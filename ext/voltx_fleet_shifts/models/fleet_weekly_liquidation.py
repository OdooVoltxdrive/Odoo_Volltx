from odoo import models, fields, api, _
from odoo.exceptions import UserError

class FleetWeeklyLiquidation(models.Model):
    _name = 'fleet.weekly.liquidation'
    _description = 'Weekly Liquidation for Fleet Drivers'
    _order = 'name desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default='New')
    contract_id = fields.Many2one('fleet.vehicle.log.contract', string='Contract', required=True)
    driver_id = fields.Many2one('res.partner', related='contract_id.purchaser_id', string='Driver', store=True)
    week_of_year = fields.Char(string='Week', required=True)

    daily_log_ids = fields.One2many('fleet.driver.daily.log', 'liquidation_id', string='Daily Logs')

    days_worked = fields.Integer(string='Days Worked', compute='_compute_totals', store=True)
    total_hours = fields.Float(string='Total Hours', compute='_compute_totals', store=True)
    amount_total = fields.Monetary(string='Total Amount', compute='_compute_totals', store=True, currency_field='currency_id')

    currency_id = fields.Many2one('res.currency', related='contract_id.company_id.currency_id')
    invoice_id = fields.Many2one('account.move', string='Invoice/Bill', readonly=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('invoiced', 'Invoiced/Billed'),
        ('paid', 'Paid')
    ], default='draft', string='Status', compute='_compute_state', store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('fleet.weekly.liquidation') or 'New'
        records = super().create(vals_list)
        for record in records:
            record._link_daily_logs()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'week_of_year' in vals or 'contract_id' in vals:
            for record in self:
                record._link_daily_logs()
        return res

    def _link_daily_logs(self):
        for liq in self:
            if liq.contract_id and liq.week_of_year:
                logs = self.env['fleet.driver.daily.log'].search([
                    ('contract_id', '=', liq.contract_id.id),
                    ('week_of_year', '=', liq.week_of_year),
                    ('liquidation_id', '=', False),
                    ('state', '=', 'done')
                ])
                if logs:
                    logs.write({'liquidation_id': liq.id})

    @api.depends('daily_log_ids.worked', 'daily_log_ids.hours_worked', 'contract_id.amount')
    def _compute_totals(self):
        for liq in self:
            worked_logs = liq.daily_log_ids.filtered(lambda l: l.worked)
            liq.days_worked = len(worked_logs)
            liq.total_hours = sum(worked_logs.mapped('hours_worked'))

            # Assuming contract.amount is the daily rate
            # In standard Odoo, amount is often recurrent cost. For this module, we interpret it as daily rate.
            daily_rate = liq.contract_id.amount if liq.contract_id else 0.0
            liq.amount_total = liq.days_worked * daily_rate

    @api.depends('invoice_id.state', 'invoice_id.payment_state')
    def _compute_state(self):
        for liq in self:
            if not liq.invoice_id:
                liq.state = 'draft'
            elif liq.invoice_id.payment_state in ('in_payment', 'paid'):
                liq.state = 'paid'
            else:
                liq.state = 'invoiced'

    def action_generate_invoice(self):
        self.ensure_one()
        if self.invoice_id:
            raise UserError(_("An invoice is already linked to this liquidation."))
        if not self.contract_id.purchaser_id:
            raise UserError(_("The contract has no driver (purchaser) assigned."))

        # Try to find a default expense account for the bill line
        journal = self.env['account.journal'].search([('type', '=', 'purchase'), ('company_id', '=', self.contract_id.company_id.id or self.env.company.id)], limit=1)
        if not journal:
            raise UserError(_("Please define a Purchase journal for the company to create Vendor Bills."))

        account = journal.default_account_id
        if not account:
            # Fallback to searching for an expense account
            account = self.env['account.account'].search([
                ('account_type', '=', 'expense'),
                ('company_id', '=', self.contract_id.company_id.id or self.env.company.id)
            ], limit=1)

        if not account:
             raise UserError(_("Please configure a default expense account on the purchase journal or create an expense account."))

        move_type = 'in_invoice'

        invoice_vals = {
            'move_type': move_type,
            'partner_id': self.driver_id.id,
            'invoice_date': fields.Date.context_today(self),
            'ref': self.name,
            'journal_id': journal.id,
            'invoice_line_ids': [(0, 0, {
                'name': f'Weekly Liquidation {self.week_of_year}',
                'quantity': self.days_worked,
                'price_unit': self.contract_id.amount, # Daily rate
                'account_id': account.id,
            })],
        }

        move = self.env['account.move'].create(invoice_vals)
        self.invoice_id = move.id

        # Mark daily logs as paid
        self.daily_log_ids.write({'state': 'paid'})

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': move.id,
            'view_mode': 'form',
            'target': 'current',
        }
