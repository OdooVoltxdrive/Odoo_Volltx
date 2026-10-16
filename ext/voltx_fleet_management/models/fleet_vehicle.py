# See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FleetVehicle(models.Model):
    _inherit = "fleet.vehicle"

    driver_slot_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="fleet_vehicle_driver_partner_rel",
        column1="vehicle_id",
        column2="partner_id",
        string="Conductores Asignados",
        domain="[('is_driver', '=', True), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="Conductores habilitados para este vehículo para la gestión de turnos.",
    )
