# -*- coding: utf-8 -*-


import logging
from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError




class ResCompany(models.Model):
    _inherit = 'res.company'

    account_payable_aux_id = fields.Many2one('account.account',company_dependent=True)
    account_receivable_aux_id = fields.Many2one('account.account',company_dependent=True)
    price_ref_div_product=fields.Boolean(string='Usar precio indexado USD del producto en facturas?',default=True,help='Este campo si es verdadero, usa el precio de venta fijado en divisa y lo lleva a Bs según la tasa Fijada en la factura')
    currency_sec_id = fields.Many2one('res.currency', default=1)
    account_igtf_id = fields.Many2one('account.account')
    account_igtf_p_id = fields.Many2one('account.account')
    #journal_transi_id = fields.Many2one('account.journal')
    percentage_cli_igtf = fields.Float(default=3)
    price_ref_div_product = fields.Boolean()
   
    #uni_neg_id = fields.Many2one('stock.unidad.negocio')