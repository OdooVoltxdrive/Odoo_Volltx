from odoo import models, fields

class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    driver_ids = fields.Many2many('res.partner', 'fleet_vehicle_driver_rel', 'vehicle_id', 'driver_id', string='Drivers')
