# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.exceptions import ValidationError

class Datospersonales(models.Model):
	_inherit = 'account.tax'# aqui con la instruccion _inherit le decimos a odoo que en la tabla datos.per se hara una inclucion o herencia
	

	aliquot = fields.Selection(selection=[
        ('no_tax_credit','No tax Credit'),
        ('exempt','Exemto'),
        ('general','Alicuota General'),
        ('reduced','Alicuota Reducida'),
        ('additional','Aliuota General + Adicional'),
        ], string='Alicuota', help='Specifies which aliquot is processed depending on the purchase book or sales book.')