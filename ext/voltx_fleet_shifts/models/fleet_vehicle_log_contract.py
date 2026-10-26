from odoo import models, fields, api, _
from odoo.exceptions import UserError


class FleetVehicleLogContract(models.Model):
    _inherit = 'fleet.vehicle.log.contract'

    # =========================================================================
    # AJUSTE 1: Redefinir purchaser_id con compute + inverse y readonly=False
    # Evita que el inspector marque 'Solo lectura: True' y acepte el chofer asignado
    # =========================================================================
    purchaser_id = fields.Many2one(
        'res.partner',
        string='Driver',
        compute='_compute_purchaser_id',
        inverse='_inverse_purchaser_id',
        store=True,
        readonly=False,
        required=True,
        tracking=True,
        help="Conductor titular único asignado a este contrato"
    )

    @api.depends('vehicle_id.driver_id')
    def _compute_purchaser_id(self):
        for contract in self:
            # Si el contrato ya tiene chofer asignado, lo preserva intacto
            if not contract.purchaser_id:
                contract.purchaser_id = contract.vehicle_id.driver_id

    def _inverse_purchaser_id(self):
        # Permite que el valor de purchaser_id sea persistente y editable
        pass

    #shift_id = fields.Many2one('fleet.work.shift', string='Shift')
    shift = fields.Char( string='Turno')
    liquidation_ids = fields.One2many('fleet.weekly.liquidation', 'contract_id', string='Weekly Liquidations')

    # Campo relacionado para los conductores del vehículo (usado para el dominio)
    vehicle_driver_ids = fields.Many2many(related='vehicle_id.driver_ids')

    # Si el usuario agregó un campo customizado cost_generate, lo forzamos a ser monetario
    cost_generate = fields.Monetary(string="Costo Generado", currency_field='secondary_currency_id')

    # Campo para obtener la moneda secundaria de la compañía (Dólar, etc.) si la hay
    secondary_currency_id = fields.Many2one(
        'res.currency',
        string='Moneda Secundaria',
        compute='_compute_secondary_currency'
    )

    def _compute_secondary_currency(self):
        for contract in self:
            usd = self.env.ref('base.USD', raise_if_not_found=False)
            contract.secondary_currency_id = usd.id if usd else contract.company_id.currency_id.id

    daily_log_ids = fields.One2many('fleet.driver.daily.log', 'contract_id', string='Daily Logs')

    daily_logs_count = fields.Integer(compute='_compute_logs_count', string='Logs Count')
    invoice_count = fields.Integer(compute='_compute_invoice_count', string='Invoice Count')

    @api.depends('daily_log_ids')
    def _compute_logs_count(self):
        for contract in self:
            contract.daily_logs_count = len(contract.daily_log_ids)

    @api.depends('liquidation_ids.invoice_id')
    def _compute_invoice_count(self):
        for contract in self:
            contract.invoice_count = len(contract.liquidation_ids.mapped('invoice_id'))

    # =========================================================================
    # AJUSTE 2: Forzar la persistencia del conductor al crear el contrato
    # =========================================================================
    @api.model_create_multi
    def create(self, vals_list):
        records = super(FleetVehicleLogContract, self).create(vals_list)
        for record, vals in zip(records, vals_list):
            driver_val = vals.get('purchaser_id') or self.env.context.get('default_purchaser_id')
            if driver_val and record.purchaser_id.id != driver_val:
                super(FleetVehicleLogContract, record).write({'purchaser_id': driver_val})
        return records

    # =========================================================================
    # AJUSTE 3: Neutralizar sobreescrituras automáticas desde el vehículo
    # =========================================================================
    def write(self, vals):
        if self.env.context.get('sync_vehicle_turn') and 'purchaser_id' in vals:
            vals = dict(vals)
            del vals['purchaser_id']
            if not vals:
                return True

        res = super(FleetVehicleLogContract, self).write(vals)

        # Si cambias manualmente el turno o el chofer en el contrato, actualiza quién conduce en el auto
        if not self.env.context.get('skip_driver_sync'):
            if any(k in vals for k in ['shift_id', 'purchaser_id', 'state']):
                for contract in self:
                    if contract.vehicle_id:
                        contract.vehicle_id.update_drivers_by_shift()
        return res

    # =========================================================================
    # AJUSTE 4: Bloquear el onchange nativo que copia el chofer del auto al contrato
    # =========================================================================
    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        saved_purchaser = self.purchaser_id
        super(FleetVehicleLogContract, self)._onchange_vehicle_id()
        if saved_purchaser:
            self.purchaser_id = saved_purchaser

    """def action_start_daily_shift(self):
        self.ensure_one()
        if not self.purchaser_id:
            raise UserError(_("El contrato no tiene un conductor asignado."))

        active_log = self.env['fleet.driver.daily.log'].search([
            ('contract_id', '=', self.id),
            ('state', 'in', ['draft', 'active'])
        ], limit=1)

        if active_log:
            active_log.action_start_shift()
        else:
            log = self.env['fleet.driver.daily.log'].create({
                'contract_id': self.id,
                'vehicle_id': self.vehicle_id.id,
                'driver_id': self.purchaser_id.id,
                'shift_id': self.shift_id.id if self.shift_id else False,
            })
            log.action_start_shift()

    def action_end_daily_shift(self):
        self.ensure_one()
        active_log = self.env['fleet.driver.daily.log'].search([
            ('contract_id', '=', self.id),
            ('state', '=', 'active')
        ], limit=1)
        if active_log:
            active_log.action_end_shift()

    def action_view_daily_logs(self):
        self.ensure_one()
        driver = self.purchaser_id
        return {
            'name': _('Daily Logs'),
            'view_mode': 'list,kanban,calendar,pivot,form',
            'res_model': 'fleet.driver.daily.log',
            'domain': [('contract_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {
                'default_contract_id': self.id,
                'default_vehicle_id': self.vehicle_id.id,
                'default_driver_id': driver.id if driver else False,
                'default_shift_id': self.shift_id.id if self.shift_id else False,
            }
        }"""

    def action_view_invoices(self):
        self.ensure_one()
        invoices = self.liquidation_ids.mapped('invoice_id')
        return {
            'name': _('Invoices'),
            'view_mode': 'list,form',
            'res_model': 'account.move',
            'domain': [('id', 'in', invoices.ids)],
            'type': 'ir.actions.act_window',
        }