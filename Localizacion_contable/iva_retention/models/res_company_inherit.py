# -*- coding: utf-8 -*-


import logging
from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError




class ResCompany(models.Model):
    _inherit = 'res.company'

    account_ret_receivable_aux_id = fields.Many2one('account.account',company_dependent=True)
    account_ret_payable_aux_id = fields.Many2one('account.account',company_dependent=True)
    journal_ret_aux_id = fields.Many2one('account.journal',company_dependent=True)
    #x_vat_retention_rate_cli =  fields.Float(default=75,company_dependent=True) 
    aplicar_ret = fields.Boolean(company_dependent=True,help='Esta opción al ser verdadero, hace que dicha compañia haga retenciones en las facturas de compras a los proveedores')
    vat_retention_rate_cli =  fields.Float(default=75,company_dependent=True,help='Este porcentaje se aplica en las facturas de ventas de clientes, si dicho cliente es agente de retencion o contribuyente especial') 
    version = fields.Char(compute='_compute_version')


    def _compute_version(self):
    	self.version='22-04-2025 Mod ret IVA firma digital'

    @api.onchange('aplicar_ret')
    def actualiza_ret_compras(self):
    	#raise UserError(_('xxx'))
    	if self.aplicar_ret==True:
	    	lista=self.env['res.partner'].search([])
	    	if lista:
	    		for det in lista:
	    			det.valores_ctas_ret()
   