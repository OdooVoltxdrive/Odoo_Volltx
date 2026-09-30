# -*- coding: utf-8 -*-


import logging
from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError




class ResCompany(models.Model):
    _inherit = 'res.company'

    account_ret_islr_receivable_aux_id = fields.Many2one('account.account',company_dependent=True)
    account_ret_islr_payable_aux_id = fields.Many2one('account.account',company_dependent=True)
    journal_ret_islr_aux_id = fields.Many2one('account.journal',company_dependent=True)
    #x_vat_retention_rate_cli =  fields.Float(default=75,company_dependent=True) 
    #aplicar_ret_islr = fields.Boolean(company_dependent=True,help='Esta opción al ser verdadero, hace que dicha compañia haga retenciones de ISLR en las facturas de compras a los proveedores')