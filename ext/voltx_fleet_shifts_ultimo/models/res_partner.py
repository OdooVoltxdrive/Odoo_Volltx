from odoo import _, api, fields, models

class ResPartner(models.Model):
    _inherit = "res.partner"

    is_driver = fields.Boolean("Es conductor")
    birth_date_drive = fields.Date("Fecha de Nacimiento")
    
    
    
