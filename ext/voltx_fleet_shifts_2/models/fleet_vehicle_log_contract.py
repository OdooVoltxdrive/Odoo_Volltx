from odoo import models, fields, api, _


class FleetVehicleLogContract(models.Model):
    _inherit = 'fleet.vehicle.log.contract'

    shift_id = fields.Many2one('fleet.work.shift', string='Shift')
    liquidation_ids = fields.One2many('fleet.weekly.liquidation', 'contract_id', string='Weekly Liquidations')

    # Campo para obtener la moneda secundaria de la compañía (Dólar, etc.) si la hay
    secondary_currency_id = fields.Many2one(
        'res.currency',
        string='Moneda Secundaria',
        compute='_compute_secondary_currency'
    )

    def _compute_secondary_currency(self):
        for contract in self:
            # En base a Odoo, se puede buscar si la empresa tiene una moneda secundaria,
            # o si hay una configuración de multimoneda.
            # Por simplicidad, tomaremos la moneda USD o la que la empresa tenga como alternativa.
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

    def action_start_daily_shift(self):
        self.ensure_one()
        # Verificar si hay un log activo para este contrato
        active_log = self.env['fleet.driver.daily.log'].search([
            ('contract_id', '=', self.id),
            ('state', 'in', ['draft', 'active'])
        ], limit=1)
        if active_log:
            active_log.action_start_shift()
        else:
            driver = self.purchaser_id or self.partner_id
            log = self.env['fleet.driver.daily.log'].create({
                'contract_id': self.id,
                'vehicle_id': self.vehicle_id.id,
                'driver_id': driver.id if driver else False,
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
        driver = self.purchaser_id or self.partner_id
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
        }

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