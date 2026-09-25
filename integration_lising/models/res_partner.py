# See LICENSE file for full copyright and licensing details.

import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):

    _inherit = "res.partner"

    is_driver = fields.Boolean("Is Driver")
    birth_date_drive = fields.Date("Fecha de Nacimiento")
    
    
    
