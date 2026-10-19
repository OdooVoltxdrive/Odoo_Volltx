from odoo import models, fields

class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    driver_slot_ids = fields.One2many('fleet.vehicle.driver.slot', 'vehicle_id', string='Driver Slots')
