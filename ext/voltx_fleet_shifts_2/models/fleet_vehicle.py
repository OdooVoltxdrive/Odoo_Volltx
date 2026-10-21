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

    def write(self, vals):
        # Capture current driver_ids before super write to compare removals
        old_driver_ids = {}
        if 'driver_ids' in vals:
            for vehicle in self:
                old_driver_ids[vehicle.id] = set(vehicle.driver_ids.ids)

        res = super(FleetVehicle, self).write(vals)

        if 'driver_ids' in vals:
            for vehicle in self:
                new_ids = set(vehicle.driver_ids.ids)
                old_ids = old_driver_ids.get(vehicle.id, set())

                added_ids = new_ids - old_ids
                removed_ids = old_ids - new_ids

                # Cerrar los logs de los conductores que fueron desasignados
                for driver_id in removed_ids:
                    active_logs = self.env['fleet.vehicle.assignation.log'].search([
                        ('vehicle_id', '=', vehicle.id),
                        ('driver_id', '=', driver_id),
                        ('date_end', '=', False),
                    ])
                    if active_logs:
                        active_logs.write({'date_end': fields.Date.today()})

                # Buscamos crear en el historial los conductores que se asignaron
                for driver_id in added_ids:
                    # Verificar si este conductor ya tiene un log activo en este vehiculo (sin fecha de fin)
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