from odoo import models, fields, api

class FleetVehicleDriverSlot(models.Model):
    _name = 'fleet.vehicle.driver.slot'
    _description = 'Fleet Vehicle Driver Slot'

    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle', required=True, ondelete='cascade')
    driver_id = fields.Many2one('res.partner', string='Driver', required=True)
    shift_id = fields.Many2one('fleet.work.shift', string='Shift', required=True)
    contract_id = fields.Many2one('fleet.vehicle.log.contract', string='Contract',
                                  domain="[('vehicle_id', '=', vehicle_id), ('purchaser_id', '=', driver_id)]")

    is_active_shift = fields.Boolean(string='Active Shift', compute='_compute_is_active_shift')

    @api.depends('vehicle_id.driver_id', 'driver_id')
    def _compute_is_active_shift(self):
        for slot in self:
            slot.is_active_shift = slot.vehicle_id.driver_id == slot.driver_id
