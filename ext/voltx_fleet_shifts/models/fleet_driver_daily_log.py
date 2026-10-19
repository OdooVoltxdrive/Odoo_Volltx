from odoo import models, fields, api
from datetime import datetime

class FleetDriverDailyLog(models.Model):
    _name = 'fleet.driver.daily.log'
    _description = 'Daily Log of Driver Journeys'

    name = fields.Char(string='Log Reference', required=True, copy=False, readonly=True, default='New')
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle', required=True)
    driver_id = fields.Many2one('res.partner', string='Driver', required=True)
    contract_id = fields.Many2one('fleet.vehicle.log.contract', string='Contract')
    shift_id = fields.Many2one('fleet.work.shift', string='Shift')

    check_in = fields.Datetime(string='Check In', default=fields.Datetime.now)
    check_out = fields.Datetime(string='Check Out')

    hours_worked = fields.Float(string='Hours Worked', compute='_compute_hours_worked', store=True)
    worked = fields.Boolean(string='Worked', default=False)

    week_of_year = fields.Char(string='Week', compute='_compute_week_of_year', store=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active (In Progress)'),
        ('done', 'Done'),
        ('paid', 'Paid')
    ], default='draft', string='Status')

    liquidation_id = fields.Many2one('fleet.weekly.liquidation', string='Weekly Liquidation')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('fleet.driver.daily.log') or 'New'
        return super().create(vals_list)

    @api.depends('check_in', 'check_out')
    def _compute_hours_worked(self):
        for log in self:
            if log.check_in and log.check_out:
                delta = log.check_out - log.check_in
                log.hours_worked = delta.total_seconds() / 3600.0
            else:
                log.hours_worked = 0.0

    @api.depends('check_in')
    def _compute_week_of_year(self):
        for log in self:
            if log.check_in:
                # Get the ISO week number
                week_num = log.check_in.isocalendar()[1]
                year = log.check_in.isocalendar()[0]
                log.week_of_year = f"W{week_num}-{year}"
            else:
                log.week_of_year = False

    def action_start_shift(self):
        self.ensure_one()
        self.check_in = fields.Datetime.now()
        self.state = 'active'
        # Assign driver to vehicle, natively Odoo tracks this in fleet.vehicle.assignation.log
        self.vehicle_id.driver_id = self.driver_id

    def action_end_shift(self):
        self.ensure_one()
        self.check_out = fields.Datetime.now()
        self.state = 'done'
        self.worked = True

    def write(self, vals):
        res = super().write(vals)
        if 'state' in vals and vals['state'] == 'done':
            # Auto-link to existing open liquidation for this week if exists
            for log in self:
                if log.contract_id and log.week_of_year and not log.liquidation_id:
                    liq = self.env['fleet.weekly.liquidation'].search([
                        ('contract_id', '=', log.contract_id.id),
                        ('week_of_year', '=', log.week_of_year)
                    ], limit=1)
                    if liq:
                        log.liquidation_id = liq.id
        return res
