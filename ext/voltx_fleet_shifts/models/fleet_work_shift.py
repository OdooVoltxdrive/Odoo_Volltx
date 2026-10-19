from odoo import models, fields

class FleetWorkShift(models.Model):
    _name = 'fleet.work.shift'
    _description = 'Fleet Work Shift'

    name = fields.Char(string='Shift Name', required=True, translate=True)
    hours_per_day = fields.Float(string='Hours per Day', required=True)
    active = fields.Boolean(default=True)
