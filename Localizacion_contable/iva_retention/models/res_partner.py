# -*- coding: utf-8 -*-

from odoo import api, fields, models,_
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError




class Partners(models.Model):
    _inherit = 'res.partner'

    #ret_agent = fields.Boolean(string='Retention agent', help='True if your partner is retention agent')
    purchase_jrl_id = fields.Many2one('account.journal', string='Purchase journal',company_dependent=False)
    sale_jrl_id = fields.Many2one('account.journal', string='Sales journal',company_dependent=False)
    ret_jrl_id = fields.Many2one('account.journal', string='Diario de Retenciones',company_dependent=True)
    vat_retention_rate = fields.Float(default=75)
    account_ret_receivable_id = fields.Many2one('account.account', string='Cuenta Retencion a Cobrar (Clientes)',company_dependent=True)
    account_ret_payable_id = fields.Many2one('account.account', string='Cuenta Retencion a Pagar (Proveedores)',company_dependent=True)
    aplicar_ret = fields.Boolean(compute='compute_aplicar_ret_company')
    vat_retention_rate_cli = fields.Float(compute='compute_aplicar_ret_company')
    contribuyente = fields.Selection([('no', 'No'),('si', 'Si')],default="no", help="Al indicar que es contribuyente especial, obliga hacer retenciones en las facturas de ventas con el '%' de retencion configurado en la compañia")

    def compute_aplicar_ret_company(self):
        self.aplicar_ret=self.env.company.aplicar_ret
        self.vat_retention_rate_cli=self.env.company.vat_retention_rate_cli



    @api.onchange('contribuyente')
    def actualiza_ctas_ret_iva(self):
    	if self.contribuyente=='si' or self.aplicar_ret==True:
    		#self.ret_agent=True
            self.valores_ctas_ret()

            

    def valores_ctas_ret(self):
        self.ret_jrl_id=self.env.company.journal_ret_aux_id.id
        self.account_ret_receivable_id=self.env.company.account_ret_receivable_aux_id.id
        self.account_ret_payable_id=self.env.company.account_ret_payable_aux_id.id
        if not self.vat_retention_rate:
            self.vat_retention_rate=75

    @api.model
    def create(self, vals):
        # Llamar al método original para crear el registro
        partner = super(Partners, self).create(vals)
        # Llamar a la función actualiza_ctas_ret_iva
        partner.actualiza_ctas_ret_iva()
        return partner