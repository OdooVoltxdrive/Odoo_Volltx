# -*- coding: utf-8 -*-


import logging
from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError




class ResCompany(models.Model):
    _inherit = 'res.company'

    
    x_ruta_txt_iva = fields.Char(default='/home/odoo/src/txt_generacion.txt')