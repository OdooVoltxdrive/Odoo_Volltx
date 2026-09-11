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
    validate_multi_tax_product = fields.Boolean(string="Validar que no se creen mas de 1 impuesto en productos",default=False)
   
    #uni_neg_id = fields.Many2one('stock.unidad.negocio')

    def write(self, vals):
        # Si el campo no viene explícitamente en la actualización del usuario, 
        # podemos asegurarnos de que al actualizar la compañía se active (o se mantenga el comportamiento deseado).
        # Para evitar bucles infinitos, validamos si ya se está actualizando este campo o usamos un contexto de control.
        if 'validate_multi_tax_product' not in vals and not self.env.context.get('skip_auto_tax_toggle'):
            # Aquí decides si deseas forzarlo a True en cada actualización o bajo cierta condición
            vals['validate_multi_tax_product'] = True
            
        return super(ResCompany, self.with_context(skip_auto_tax_toggle=True)).write(vals)