from odoo import models, fields, api


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    driver_ids = fields.Many2many(
        'res.partner',
        'fleet_vehicle_driver_rel',
        'vehicle_id',
        'driver_id',
        string='Conductores Asignados',
        domain=[('is_driver', '=', True)]
    )

    current_shift_driver_id = fields.Many2one(
        'res.partner',
        string='Conductor en Turno',
        help="Conductor asignado al turno"
    )

    next_shift_driver_id = fields.Many2one(
        'res.partner',
        string='Próximo Conductor',
        help="Conductor asignado al siguiente turno"
    )

    # Nuevo historial propio
    custom_driver_history_ids = fields.One2many(
        'fleet.vehicle.driver.history',
        'vehicle_id',
        string='Historial de Conductores'
    )
    custom_driver_history_count = fields.Integer(
        string='Nro Conductores Histórico',
        compute='_compute_custom_driver_history_count'
    )

    @api.depends('custom_driver_history_ids')
    def _compute_custom_driver_history_count(self):
        for vehicle in self:
            vehicle.custom_driver_history_count = len(vehicle.custom_driver_history_ids)

    def action_open_custom_driver_history(self):
        self.ensure_one()
        return {
            'name': 'Historial de Asignaciones',
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.vehicle.driver.history',
            'view_mode': 'list,form',
            'domain': [('vehicle_id', '=', self.id)],
            'context': {'default_vehicle_id': self.id},
        }

    @api.model_create_multi
    def create(self, vals_list):
        records = super(FleetVehicle, self).create(vals_list)
        for vehicle in records:
            if vehicle.driver_ids:
                for driver in vehicle.driver_ids:
                    # Registrar en el nuevo historial
                    self.env['fleet.vehicle.driver.history'].create({
                        'vehicle_id': vehicle.id,
                        'driver_id': driver.id,
                        'date_start': fields.Date.today(),
                    })

                    # Contrato individual con purchaser_id asegurado
                    existing_contract = self.env['fleet.vehicle.log.contract'].search([
                        ('vehicle_id', '=', vehicle.id),
                        ('purchaser_id', '=', driver.id),
                        ('state', 'in', ['open', 'futur']),
                    ], limit=1)

                    if not existing_contract:
                        self.env['fleet.vehicle.log.contract'].with_context(
                            default_purchaser_id=driver.id,
                            sync_vehicle_turn=True,
                            tracking_disable=True,
                            mail_create_nolog=True
                        ).create({
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

        contracts_before = {}
        if 'driver_id' in vals:
            for vehicle in self:
                contracts = self.env['fleet.vehicle.log.contract'].search([
                    ('vehicle_id', '=', vehicle.id),
                    ('state', 'in', ['open', 'futur']),
                ])
                contracts_before[vehicle.id] = [(c, c.purchaser_id.id) for c in contracts if c.purchaser_id]

        res = super(FleetVehicle, self.with_context(sync_vehicle_turn=True)).write(vals)

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

                # CONDUCTORES REMOVIDOS: Se sella la fecha fin en el historial sin borrar nada
                for driver_id in removed_ids:
                    active_logs = self.env['fleet.vehicle.driver.history'].search([
                        ('vehicle_id', '=', vehicle.id),
                        ('driver_id', '=', driver_id),
                        ('date_end', '=', False),
                    ])
                    if active_logs:
                        active_logs.write({'date_end': fields.Date.today()})

                # CONDUCTORES AÑADIDOS: Crear historial y contrato individual
                for driver_id in added_ids:
                    existing_log = self.env['fleet.vehicle.driver.history'].search([
                        ('vehicle_id', '=', vehicle.id),
                        ('driver_id', '=', driver_id),
                        ('date_end', '=', False),
                    ], limit=1)

                    if not existing_log:
                        self.env['fleet.vehicle.driver.history'].create({
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

        return res