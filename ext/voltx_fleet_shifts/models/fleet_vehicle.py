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

    current_shift_driver_id = fields.Many2one(
        'res.partner',
        string='Conductor en Turno',
        help="Conductor asignado al turno que está transcurriendo en este momento"
    )

    next_shift_driver_id = fields.Many2one(
        'res.partner',
        string='Próximo Conductor',
        help="Conductor asignado al siguiente turno de la jornada"
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super(FleetVehicle, self).create(vals_list)
        for vehicle in records:
            if vehicle.driver_ids:
                for driver in vehicle.driver_ids:
                    # 1. Crear registro en el historial de asignaciones
                    self.env['fleet.vehicle.assignation.log'].create({
                        'vehicle_id': vehicle.id,
                        'driver_id': driver.id,
                        'date_start': fields.Date.today(),
                    })

                    # 2. Creación obligada del contrato individual con su respectivo purchaser_id
                    contract_vals = {
                        'vehicle_id': vehicle.id,
                        'purchaser_id': driver.id,
                        'state': 'open',
                        'cost_subtype_id': self.env.ref('fleet.type_contract_leasing', raise_if_not_found=False).id if self.env.ref('fleet.type_contract_leasing', raise_if_not_found=False) else False,
                    }
                    
                    ### === CAMBIO 1: Se añade 'sync_vehicle_turn': True para coordinar con el modelo contrato ===
                    self.env['fleet.vehicle.log.contract'].with_context(
                        default_purchaser_id=driver.id,
                        sync_vehicle_turn=True,
                        tracking_disable=True,
                        mail_create_nolog=True
                    ).create(contract_vals)

                # 3. Calcular quién conduce según turno
                vehicle.update_drivers_by_shift()
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

        ### === CAMBIO 2: Pasamos sync_vehicle_turn=True en el super() para que no arrastre contratos ===
        res = super(FleetVehicle, self.with_context(sync_vehicle_turn=True)).write(vals)

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
                        ### === CAMBIO 3: Aquí se aplica with_context exactamente igual que en create ===
                        # Anteriormente se creaba sin contexto y Odoo borraba el purchaser_id
                        self.env['fleet.vehicle.log.contract'].with_context(
                            default_purchaser_id=driver_id,
                            sync_vehicle_turn=True,
                            tracking_disable=True,
                            mail_create_nolog=True
                        ).create({
                            'vehicle_id': vehicle.id,
                            'purchaser_id': driver_id,
                            'state': 'open',
                            'cost_subtype_id': self.env.ref('fleet.type_contract_leasing', raise_if_not_found=False).id if self.env.ref('fleet.type_contract_leasing', raise_if_not_found=False) else False,
                        })

                vehicle.update_drivers_by_shift()

        return res

    """def _get_current_time_and_day(self):
        #Retorna el día de la semana (0=Lun, 6=Dom) y la hora float con base en la zona horaria del usuario/empresa.
        tz_name = self.env.user.tz or self.env.company.partner_id.tz or 'UTC'
        user_tz = pytz.timezone(tz_name)
        now_dt = datetime.now(user_tz)
        current_hour = now_dt.hour + (now_dt.minute / 60.0)
        return now_dt.weekday(), current_hour

    def _is_shift_matching(self, shift, weekday, current_hour):
        #Valida si un turno coincide con el día y la hora consultada.
        if not shift:
            return False
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
        #Actualiza current_shift_driver_id y next_shift_driver_id sin tocar driver_id.
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
                driver = contract.purchaser_id
                if not driver:
                    continue

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
                next_driver = closest_contract.purchaser_id

            # Si no coinciden horarios pero hay conductores asignados
            if not current_driver and vehicle.driver_ids:
                current_driver = vehicle.driver_ids[0]
                if len(vehicle.driver_ids) > 1:
                    next_driver = vehicle.driver_ids[1]

            vals = {}
            if vehicle.current_shift_driver_id != current_driver:
                vals['current_shift_driver_id'] = current_driver.id if current_driver else False
            if vehicle.next_shift_driver_id != next_driver:
                vals['next_shift_driver_id'] = next_driver.id if next_driver else False

            if vals:
                # Escribimos exclusivamente en los campos nuevos
                super(FleetVehicle, vehicle).write(vals)"""



    def _get_current_time_and_day(self):
        """Retorna el día de la semana (0=Lun, 6=Dom) y la hora float según la zona horaria del usuario o compañía."""
        tz_name = self.env.user.tz or self.env.company.partner_id.tz or 'UTC'
        user_tz = pytz.timezone(tz_name)
        now_dt = datetime.now(user_tz)
        current_hour = now_dt.hour + (now_dt.minute / 60.0)
        return now_dt.weekday(), current_hour

    def _is_shift_matching(self, shift, weekday, current_hour):
        """Valida si un turno coincide estrictamente con el día y la jornada horaria consultada."""
        if not shift:
            return False

        # --- A. Turno Diurno estándar (ej. 06:00 a 14:00) ---
        if shift.end_hour > shift.start_hour:
            # 1. Validar horario
            if not (shift.start_hour <= current_hour < shift.end_hour):
                return False
            # 2. Validar día de aplicación
            if shift.applies_on == 'weekdays' and weekday >= 5:
                return False
            if shift.applies_on == 'weekends' and weekday < 5:
                return False
            return True

        # --- B. Turno Nocturno con cruce de medianoche (ej. 20:00 a 06:00) ---
        else:
            # 1. Validar horario
            if not (current_hour >= shift.start_hour or current_hour < shift.end_hour):
                return False

            # 2. Determinar el día en que arrancó la jornada
            # Si estamos en la madrugada (ej. 02:00 < 06:00), el turno empezó el día anterior
            origin_day = (weekday - 1) % 7 if current_hour < shift.end_hour else weekday

            if shift.applies_on == 'weekdays' and origin_day >= 5:
                return False
            if shift.applies_on == 'weekends' and origin_day < 5:
                return False
            return True

    def _shift_applies_today(self, shift, weekday):
        """Valida si un turno tiene operaciones programadas para el día actual."""
        if not shift:
            return False
        if shift.applies_on == 'all':
            return True
        if shift.applies_on == 'weekdays':
            return weekday < 5
        if shift.applies_on == 'weekends':
            return weekday >= 5
        return False

    def update_drivers_by_shift(self):
        """Actualiza current_shift_driver_id y next_shift_driver_id respetando días y horas reales."""
        weekday, current_hour = self._get_current_time_and_day()

        for vehicle in self:
            contracts = self.env['fleet.vehicle.log.contract'].search([
                ('vehicle_id', '=', vehicle.id),
                ('state', '=', 'open'),
                ('shift_id', '!=', False)
            ])

            if not contracts:
                if vehicle.current_shift_driver_id or vehicle.next_shift_driver_id:
                    super(FleetVehicle, vehicle).write({
                        'current_shift_driver_id': False,
                        'next_shift_driver_id': False
                    })
                continue

            current_driver = False
            upcoming_contracts = []

            for contract in contracts:
                driver = contract.purchaser_id
                shift = contract.shift_id
                if not driver or not shift:
                    continue

                # 1. Comprobar si está en turno activo en este momento
                if self._is_shift_matching(shift, weekday, current_hour):
                    current_driver = driver
                else:
                    # 2. Solo considerarlo como próximo si el turno aplica para el día de hoy
                    if self._shift_applies_today(shift, weekday):
                        upcoming_contracts.append(contract)

            # 3. Determinar el próximo conductor del día (el turno más próximo por comenzar)
            next_driver = False
            if upcoming_contracts:
                closest_contract = min(
                    upcoming_contracts,
                    key=lambda c: (c.shift_id.start_hour - current_hour) % 24
                )
                next_driver = closest_contract.purchaser_id

            # 4. Asignación directa (sin fallback forzado que viole las reglas de turnos)
            vals = {}
            target_current_id = current_driver.id if current_driver else False
            target_next_id = next_driver.id if next_driver else False

            if vehicle.current_shift_driver_id.id != target_current_id:
                vals['current_shift_driver_id'] = target_current_id
            if vehicle.next_shift_driver_id.id != target_next_id:
                vals['next_shift_driver_id'] = target_next_id

            if vals:
                super(FleetVehicle, vehicle).write(vals)