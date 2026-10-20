from odoo import models, fields, api, _

class FleetVehicleLogContract(models.Model):
    _inherit = 'fleet.vehicle.log.contract'

    shift_id = fields.Many2one('fleet.work.shift', string='Shift')
    liquidation_ids = fields.One2many('fleet.weekly.liquidation', 'contract_id', string='Weekly Liquidations')
    daily_log_ids = fields.One2many('fleet.driver.daily.log', 'contract_id', string='Daily Logs')

    daily_logs_count = fields.Integer(compute='_compute_logs_count')
    invoice_count = fields.Integer(compute='_compute_invoice_count')

    @api.depends('daily_log_ids')
    def _compute_logs_count(self):
        for contract in self:
            contract.daily_logs_count = len(contract.daily_log_ids)

    @api.depends('liquidation_ids.invoice_id')
    def _compute_invoice_count(self):
        for contract in self:
            contract.invoice_count = len(contract.liquidation_ids.mapped('invoice_id'))

    def action_view_daily_logs(self):
        self.ensure_one()
        return {
            'name': _('Daily Logs'),
            'view_mode': 'list,form,calendar,pivot,kanban',
            'res_model': 'fleet.driver.daily.log',
            'domain': [('contract_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_contract_id': self.id, 'default_vehicle_id': self.vehicle_id.id, 'default_driver_id': self.purchaser_id.id}
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
