# -*- coding: utf-8 -*-


from odoo import api, fields, models,api, _




class Partners(models.Model):
    _inherit = 'res.partner'

    ret_agent_isrl= fields.Boolean(string='Retention agent ISLR', help='True if your partner is retention agent',company_dependent=True)
    sale_isrl_id = fields.Many2one('account.journal', string='Journal',company_dependent=True)
    account_isrl_receivable_id = fields.Many2one('account.account', string='Cuenta ISLR Retencion a Cobrar (Clientes)',company_dependent=True)
    account_isrl_payable_id = fields.Many2one('account.account', string='Cuenta ISLR Retencion a Pagar (Proveedores)',company_dependent=True)
    #firma = fields.Binary(string='Firma y Sello')

    @api.onchange('ret_agent_isrl')
    def carga_ctas(self):
    	if self.ret_agent_isrl==True:
    		self.sale_isrl_id=self.env.company.journal_ret_islr_aux_id.id
    		self.account_isrl_payable_id=self.env.company.account_ret_islr_payable_aux_id.id
    		self.account_isrl_receivable_id=self.env.company.account_ret_islr_receivable_aux_id.id
    	else:
    		self.sale_isrl_id = False
    		self.account_isrl_payable_id = False
    		self.account_isrl_receivable_id = False
    