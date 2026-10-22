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
                vehicle._sync_assigned_drivers(vehicle.driver_ids.ids, [])
                vehicle.update_drivers_by_shift()
        return records

    def write(self, vals):
        old_driver_ids = {}
        if 'driver_ids' in vals:
            for vehicle in self:
                old_driver_ids[vehicle.id] = set(vehicle.driver_ids.ids)

        res = super(FleetVehicle, self).write(vals)

        if 'driver_ids' in vals:
            for vehicle in self:
                new_ids = set(vehicle.driver_ids.ids)
                old_ids = old_driver_ids.get(vehicle.id, set())

                added_ids = list(new_ids - old_ids)
                removed_ids = list(old_ids - new_ids)

                vehicle._sync_assigned_drivers(added_ids, removed_ids)
                vehicle.update_drivers_by_shift()

        return res

    def _sync_assigned_drivers(self, added_ids, removed_ids):
        self.ensure_one()

        if removed_ids:
            active_logs = self.env['fleet.vehicle.assignation.log'].search([
                ('vehicle_id', '=', self.id),
                ('driver_id', 'in', removed_ids),
                ('date_end', '=', False),
            ])
            if active_logs:
                active_logs.write({'date_end': fields.Date.today()})

        for index, driver_id in enumerate(added_ids):
            # Historial
            existing_log = self.env['fleet.vehicle.assignation.log'].search([
                ('vehicle_id', '=', self.id),
                ('driver_id', '=', driver_id),
                ('date_end', '=', False),
            ], limit=1)
            if not existing_log:
                self.env['fleet.vehicle.assignation.log'].create({
                    'vehicle_id': self.id,
                    'driver_id': driver_id,
                    'date_start': fields.Date.today(),
                })

            # Contrato
            existing_contract = self.env['fleet.vehicle.log.contract'].search([
                ('vehicle_id', '=', self.id),
                ('purchaser_id', '=', driver_id),
                ('state', 'in', ['futur', 'open'])
            ], limit=1)

            if not existing_contract:
                contract_type = self.env.ref('fleet.type_contract_leasing', raise_if_not_found=False)

                # ==========================================
                # [PRUEBA 1]: ASIGNACIÓN DE TURNO AUTOMÁTICO
                # ==========================================
                test_shift = False
                all_shifts = self.env['fleet.work.shift'].search([], order='start_hour asc')
                if all_shifts:
                    # Asigna el turno 1 al primer conductor y el turno 2 al segundo
                    test_shift = all_shifts[index % len(all_shifts)].id

                self.env['fleet.vehicle.log.contract'].create({
                    'vehicle_id': self.id,
                    'purchaser_id': driver_id,
                    'state': 'open',
                    'cost_subtype_id': contract_type.id if contract_type else False,
                    # LÍNEA DE PRUEBA:
                    'shift_id': test_shift, 
                })

    def _get_current_time_and_day(self):
        """Calcula el día y la hora."""
        # ==========================================
        # [PRUEBA 2]: HORA FIJA MANUAL SIMULADA
        # ==========================================
        # 0 = Lunes | 10.0 = 10:00 AM (Cambiar a 16.0 para simular la tarde)
        return 0, 10.0  # <-- ESTA LÍNEA FUERZA LA PRUEBA

        # Código real en segundo plano:
        tz_name = self.env.user.tz or self.env.company.partner_id.tz or 'UTC'
        user_tz = pytz.timezone(tz_name)
        now_dt = datetime.now(user_tz)
        current_hour = now_dt.hour + (now_dt.minute / 60.0)
        return now_dt.weekday(), current_hour

    def _is_shift_matching(self, shift, weekday, current_hour):
        if not shift:
            return False
        if shift.applies_on == 'weekdays' and weekday >= 5:
            return False
        if shift.applies_on == 'weekends' and weekday < 5:
            return False
        if shift.end_hour > shift.start_hour:
            return shift.start_hour <= current_hour < shift.end_hour
        else:
            return current_hour >= shift.start_hour or current_hour < shift.end_hour

    def update_drivers_by_shift(self):
        weekday, current_hour = self._get_current_time_and_day()

        for vehicle in self:
            contracts = self.env['fleet.vehicle.log.contract'].search([
                ('vehicle_id', '=', vehicle.id),
                ('state', '=', 'open'),
                ('purchaser_id', '!=', False),
            ])
            if not contracts:
                continue

            current_driver = False
            next_driver = False

            shift_contracts = contracts.filtered(lambda c: c.shift_id)
            if shift_contracts:
                active_contract = False
                upcoming_candidates = []

                for contract in shift_contracts:
                    if self._is_shift_matching(contract.shift_id, weekday, current_hour):
                        active_contract = contract
                    else:
                        upcoming_candidates.append(contract)

                if active_contract:
                    current_driver = active_contract.purchaser_id

                if upcoming_candidates:
                    closest_contract = min(
                        upcoming_candidates,
                        key=lambda c: (c.shift_id.start_hour - current_hour) % 24
                    )
                    next_driver = closest_contract.purchaser_id

            if not current_driver and vehicle.driver_ids:
                current_driver = vehicle.driver_ids[0]
                if len(vehicle.driver_ids) > 1:
                    next_driver = vehicle.driver_ids[1]

            vals = {}
            if current_driver and vehicle.driver_id != current_driver:
                vals['driver_id'] = current_driver.id
            if vehicle.future_driver_id != next_driver:
                vals['future_driver_id'] = next_driver.id if next_driver else False

            if vals:
                super(FleetVehicle, vehicle).write(vals)