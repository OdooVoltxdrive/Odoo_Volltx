from datetime import datetime
import pytz
from odoo import models, fields, api


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    driver_ids = fields.Many2many(
        'res.partner',
        'fleet_vehicle_driver_rel',
        'vehicle_id',
        'driver_id',
        string='Conductores Asignados'
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super(FleetVehicle, self).create(vals_list)
        for vehicle in records:
            if vehicle.driver_ids:
                for driver in vehicle.driver_ids:
                    # Crear en historial
                    self.env['fleet.vehicle.assignation.log'].create({
                        'vehicle_id': vehicle.id,
                        'driver_id': driver.id,
                        'date_start': fields.Date.today(),
                    })
                    # Creación automática de contrato
                    self.env['fleet.vehicle.log.contract'].create({
                        'vehicle_id': vehicle.id,
                        'purchaser_id': driver.id,
                        'state': 'open',
                        'cost_subtype_id': self.env.ref('fleet.type_contract_leasing', raise_if_not_found=False).id if self.env.ref('fleet.type_contract_leasing', raise_if_not_found=False) else False,
                    })
        return records

    def write(self, vals):
        old_driver_ids = {}
        if 'driver_ids' in vals:
            for vehicle in self:
                old_driver_ids[vehicle.id] = set(vehicle.driver_ids.ids)

        # -------------------------------------------------------------------------
        # BLOQUEO CLAVE: Si Odoo o el usuario cambia el driver_id del vehículo,
        # guardamos los purchaser_id actuales de los contratos para restaurarlos
        # si Odoo intenta sobreescribirlos de forma masiva en el super().
        # -------------------------------------------------------------------------
        contracts_before = {}
        if 'driver_id' in vals:
            for vehicle in self:
                contracts = self.env['fleet.vehicle.log.contract'].search([
                    ('vehicle_id', '=', vehicle.id),
                    ('state', 'in', ['open', 'futur']),
                ])
                contracts_before[vehicle.id] = [(c, c.purchaser_id.id) for c in contracts if c.purchaser_id]

        res = super(FleetVehicle, self).write(vals)

        # Restaurar el conductor original de cada contrato si Odoo base los alteró
        if contracts_before:
            for vehicle_id, contract_data in contracts_before.items():
                for contract, original_purchaser_id in contract_data:
                    if contract.exists() and contract.purchaser_id.id != original_purchaser_id:
                        super(models.Model, contract).write({'purchaser_id': original_purchaser_id})

        if 'driver_ids' in vals:
            for vehicle in self:
                new_ids = set(vehicle.driver_ids.ids)
                old_ids = old_driver_ids.get(vehicle.id, set())

                added_ids = new_ids - old_ids
                removed_ids = old_ids - new_ids

                # Cerrar los logs de los conductores desasignados
                for driver_id in removed_ids:
                    active_logs = self.env['fleet.vehicle.assignation.log'].search([
                        ('vehicle_id', '=', vehicle.id),
                        ('driver_id', '=', driver_id),
                        ('date_end', '=', False),
                    ])
                    if active_logs:
                        active_logs.write({'date_end': fields.Date.today()})

                # Crear logs y contratos para los conductores añadidos
                for driver_id in added_ids:
                    existing_log = self.env['fleet.vehicle.assignation.log'].search([
                        ('vehicle_id', '=', vehicle.id),
                        ('driver_id', '=', driver_id),
                        ('date_end', '=', False),
                    ], limit=1)

                    if not existing_log:
                        self.env['fleet.vehicle.assignation.log'].create({
                            'vehicle_id': vehicle.id,
                            'driver_id': driver_id,
                            'date_start': fields.Date.today(),
                        })

                    existing_contract = self.env['fleet.vehicle.log.contract'].search([
                        ('vehicle_id', '=', vehicle.id),
                        ('purchaser_id', '=', driver_id),
                        ('state', 'in', ['futur', 'open'])
                    ], limit=1)

                    if not existing_contract:
                        self.env['fleet.vehicle.log.contract'].create({
                            'vehicle_id': vehicle.id,
                            'purchaser_id': driver_id,
                            'state': 'open',
                            'cost_subtype_id': self.env.ref('fleet.type_contract_leasing', raise_if_not_found=False).id if self.env.ref('fleet.type_contract_leasing', raise_if_not_found=False) else False,
                        })

                vehicle.update_drivers_by_shift()

        return res

    def _get_current_time_and_day(self):
        """Retorna el día de la semana (0=Lun, 6=Dom) y la hora float con base en la zona horaria del usuario/empresa."""
        tz_name = self.env.user.tz or self.env.company.partner_id.tz or 'UTC'
        user_tz = pytz.timezone(tz_name)
        now_dt = datetime.now(user_tz)
        current_hour = now_dt.hour + (now_dt.minute / 60.0)
        return now_dt.weekday(), current_hour

    def _is_shift_matching(self, shift, weekday, current_hour):
        """Valida si un turno coincide con el día y la hora consultada."""
        # 0=Lunes, 4=Viernes, 5=Sábado, 6=Domingo
        if shift.applies_on == 'weekdays' and weekday >= 5:
            return False
        if shift.applies_on == 'weekends' and weekday < 5:
            return False

        if shift.end_hour > shift.start_hour:
            return shift.start_hour <= current_hour < shift.end_hour
        else:
            # Turno que cruza la medianoche
            return current_hour >= shift.start_hour or current_hour < shift.end_hour

    def update_drivers_by_shift(self):
        """Evalúa los contratos abiertos con turno y actualiza driver_id y future_driver_id."""
        weekday, current_hour = self._get_current_time_and_day()

        for vehicle in self:
            contracts = self.env['fleet.vehicle.log.contract'].search([
                ('vehicle_id', '=', vehicle.id),
                ('state', '=', 'open'),
                ('shift_id', '!=', False)
            ])

            if not contracts:
                continue

            current_driver = False
            upcoming_contracts = []

            for contract in contracts:
                driver = contract.purchaser_id or contract.partner_id
                if self._is_shift_matching(contract.shift_id, weekday, current_hour):
                    current_driver = driver
                else:
                    upcoming_contracts.append(contract)

            next_driver = False
            if upcoming_contracts:
                closest_contract = min(
                    upcoming_contracts,
                    key=lambda c: (c.shift_id.start_hour - current_hour) % 24
                )
                next_driver = closest_contract.purchaser_id or closest_contract.partner_id

            vals = {}
            if current_driver and vehicle.driver_id != current_driver:
                vals['driver_id'] = current_driver.id
            if vehicle.future_driver_id != next_driver:
                vals['future_driver_id'] = next_driver.id if next_driver else False

            if vals:
                vehicle.write(vals)