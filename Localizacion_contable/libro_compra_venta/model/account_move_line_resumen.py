# -*- coding: utf-8 -*-


import logging
from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

bypass_token = object()
DOMAINS = {
    'account.move': lambda operator, value: [('company_id.check_account_audit_trail', operator, value)],
    'account.account': lambda operator, value: [('company_ids.check_account_audit_trail', operator, value)],
    'account.tax': lambda operator, value: [('company_id.check_account_audit_trail', operator, value)],
    'res.partner': lambda operator, value: [
        '|', ('company_id', '=', False), ('company_id.check_account_audit_trail', operator, value),
        '|', ('customer_rank', '>', 0), ('supplier_rank', '>', 0),
    ],
    'res.company': lambda operator, value: [('check_account_audit_trail', operator, value)],
}




class ResumenAlicuota(models.Model):
    _name = 'account.move.line.resumen'

    invoice_id = fields.Many2one('account.move', ondelete='cascade')
    move_type = fields.Char()
    base_exenta=fields.Float()
    base_general=fields.Float()
    impuesto_general=fields.Float()
    retencion_general=fields.Float()
    base_reducida=fields.Float()
    impuesto_reducida=fields.Float()
    retencion_reducida=fields.Float()
    base_adicional=fields.Float()
    impuesto_adicional=fields.Float()
    retencion_adicional=fields.Float()
    total_fact = fields.Float()
    tipo_doc=fields.Char()
    state=fields.Char()
    vat_ret_id=fields.Many2one('vat.retention', string='Nro de Comprobante IVA')
    state_voucher_iva=fields.Char()
    fecha_fact= fields.Date()
    fecha_comprobante= fields.Date()
    company_id = fields.Many2one('res.company','Company',default=lambda self: self.env.company.id)




class AccountMove(models.Model):
    _inherit = 'account.move'

    alicuota_line_ids = fields.One2many('account.move.line.resumen', 'invoice_id', string='Resumen')

    
    @api.constrains('state')
    def resum(self):
        for selff in self:
            if selff.move_type!='entry' and selff.state=='posted':
                selff.resumen()


    def resumen(self):
        for selff in self:
            if selff:
                if selff.journal_id.nota_entrega!=True:
                    base_general=base_reducida=base_adicional=base_exenta=0
                    impuesto_general=impuesto_reducida=impuesto_adicional=0
                    if selff.move_type=='in_invoice' or selff.move_type=='out_invoice':
                        tipo_doc="01"
                    if selff.state=='cancel':
                        tipo_doc="03"
                    if selff.move_type in ('in_receipt','out_receipt','in_refund','out_refund'):
                        tipo_doc="02"
                    #raise UserError(_('move_type = %s ')%self.id)
                    #if not tipo_doc:
                        #tipo_doc='01'
                    base_general=0
                    impuesto_general=0
                    base_reducida=0
                    impuesto_reducida=0
                    base_adicional=0
                    impuesto_adicional=0
                    base_exenta=0
                    total_fact=0
                    if selff.state!='cancel':
                        for linea_fact in selff.invoice_line_ids.search([('move_id','=',selff.id)]):
                            if linea_fact.tax_ids.aliquot=='general':
                                base_general=base_general+linea_fact.price_subtotal
                                impuesto_general=impuesto_general+(linea_fact.price_total-linea_fact.price_subtotal)
                            if linea_fact.tax_ids.aliquot=='reduced':
                                base_reducida=base_reducida+linea_fact.price_subtotal
                                impuesto_reducida=impuesto_reducida+(linea_fact.price_total-linea_fact.price_subtotal)
                            if linea_fact.tax_ids.aliquot=='additional':
                                base_adicional=base_adicional+linea_fact.price_subtotal
                                impuesto_adicional=impuesto_adicional+(linea_fact.price_total-linea_fact.price_subtotal)
                            if linea_fact.tax_ids.aliquot=='exempt' and linea_fact.linea_exenta==False:
                                base_exenta=base_exenta+linea_fact.price_subtotal
                        total_fact=selff.amount_total
                    values={
                    'invoice_id':selff.id,
                    'move_type':selff.move_type,
                    'base_exenta':-1*base_exenta if selff.move_type in ('in_refund','out_refund') else base_exenta,
                    'base_general':-1*base_general if selff.move_type in ('in_refund','out_refund') else base_general,
                    'impuesto_general':-1*impuesto_general if selff.move_type in ('in_refund','out_refund') else impuesto_general,
                    'base_reducida':-1*base_reducida if selff.move_type in ('in_refund','out_refund') else base_reducida,
                    'impuesto_reducida':-1*impuesto_reducida if selff.move_type in ('in_refund','out_refund') else impuesto_reducida,
                    'base_adicional':-1*base_adicional if selff.move_type in ('in_refund','out_refund') else base_adicional,
                    'impuesto_adicional':-1*impuesto_adicional if selff.move_type in ('in_refund','out_refund') else impuesto_adicional,
                    'state':selff.state,
                    'vat_ret_id':selff.vat_ret_id.id,
                    'fecha_fact':selff.date,
                    'tipo_doc':tipo_doc,
                    'total_fact':-1*total_fact if selff.move_type in ('in_refund','out_refund') else total_fact,
                    }
                    selff.env['account.move.line.resumen'].create(values)



    def _nro_comp(self):
        self.nro_comprobante=self.vat_ret_id.name



    def button_draft(self):
        super().button_draft()
        for selff in self:
            temporal=selff.env['account.move.line.resumen'].search([('invoice_id','=',selff.id)])
            temporal.with_context(force_delete=True).unlink()

    def button_cancel(self):
        super().button_cancel()
        self.state='cancel'
        self.resumen()

    def anular(self):
        var=''
        var=self.env.user.x_llevar_borra_fact
        self.env.user.x_llevar_borra_fact='si'
        self.button_draft()
        self.button_cancel()
        self.env.user.x_llevar_borra_fact=var

    def anular_temp2(self):
        lista=self.env['product.product'].search([('standard_price','=',0)])
        cant=len(lista)
        #raise UserError(_('Cantidad = %s ')%cant)
        for det in lista:
            det.standard_price=0.5



    def anular_temp(self):
        lista=self.env['product.category'].search([])
        cant=len(lista)
        #raise UserError(_('Cantidad = %s ')%cant)
        for det in lista:
            det.property_account_income_categ_id=764
            det.property_account_expense_categ_id=772
            det.property_stock_valuation_account_id=772
            det.property_stock_account_input_categ_id=688
            det.property_stock_account_output_categ_id=688
            det.property_stock_journal=8
            det.property_cost_method='average'
            det.property_valuation='real_time'
