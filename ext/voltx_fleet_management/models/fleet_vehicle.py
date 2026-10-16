# See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FleetVehicle(models.Model):
    _inherit = "fleet.vehicle"

    driver_slot_ids = fields.One2many(
        'res.partner',
        string='Conductores por Turno'
    )

