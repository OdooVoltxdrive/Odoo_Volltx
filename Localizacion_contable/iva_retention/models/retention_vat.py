# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime


_logger = logging.getLogger('__name__')


class RetentionVat(models.Model):
    """This is a main model for rentetion vat control."""
    _name = 'vat.retention'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    journal_id=fields.Many2one('account.journal')
    name = fields.Char(string='Voucher number', default='00000000')
    # datos del proveedor
    partner_id = fields.Many2one('res.partner', string='Partner')
    rif = fields.Char(string='RIF',compute='_compute_rif')
    # datos de emision y entrega del comprobante
    accouting_date = fields.Date(string='Accounting date', help='Voucher generation date', readonly=True)
    voucher_delivery_date = fields.Date(string='Voucher delivery date')
    # datos de la factura
    invoice_id = fields.Many2one('account.move', string="Invoice")
    invoice_number_next = fields.Char(string='Invoice Number')
    invoice_number_control = fields.Char(string='Invoice control number')

    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)

    # totales
    amount_untaxed = fields.Float(string='Importe Base', help='This concept is tax base', compute='_compute_base_imponible')
    vat_retentioned = fields.Float(string='Monto Retenido',compute='_compute_vat_retentioned')

    #datos contables
    currency_id = fields.Many2one('res.currency', string='Currency',default=lambda self: self.env.company.currency_id.id)
    account_id = fields.Many2one('account.account', string='Account')
    asiento_ret_iva_id = fields.Many2one('account.move')
    state = fields.Selection(selection=[
            ('draft', 'Borrador'),
            ('posted', 'Publicado'),
            # ('done', 'Done'),
            ('cancel', 'Anulado')
        ], string='Status', readonly=True, copy=False, tracking=True,
        default='draft')

    type = fields.Selection(selection=[
        ('out_invoice', 'Factura Cliente'),
        ('in_invoice','Factura Proveedor'),
        ('in_refund','Nota Crédito Proveedor'),
        ('out_refund','Nota Crédito Cliente'),
        ('in_receipt','Nota Débito Proveedor'),
        ('out_receipt','Nota Débito Cliente'),
        ], string="Tipo de Documento")

    retention_line_ids = fields.One2many('vat.retention.invoice.line', 'retention_id', string='Lineas de retenciones')

    def action_posted(self):
        if self.name=='00000000' and self.type in ('in_invoice','in_refund','in_receipt'):
            # solo para proveedor
            self.name=self.asigna_nro_voicher()
        self.state='posted'
        self.create_asiento()
        if self.invoice_id.amount_residual!=0:
            self.create_conciliacion_ret_iva()

    def _compute_rif(self):
        self.rif= self.partner_id.vat


    def create_asiento(self):
        # proveedores
        if self.type in ('in_invoice','in_receipt'):
            account_cred_id=self.partner_id.account_ret_payable_id.id
            account_debi_id=self.partner_id.property_account_payable_id.id
        if self.type=='in_refund':
            account_cred_id=self.partner_id.property_account_payable_id.id
            account_debi_id=self.partner_id.account_ret_payable_id.id
        # clientes
        if self.type in ('out_invoice','out_receipt'):
            account_cred_id=self.partner_id.property_account_receivable_id.id
            account_debi_id=self.partner_id.account_ret_receivable_id.id
        if self.type=='out_refund':
            account_cred_id=self.partner_id.account_ret_receivable_id.id
            account_debi_id=self.partner_id.property_account_receivable_id.id
        vals=({
            'name':self.nro_asiento_comp_ret_iva(),
            'date':self.accouting_date,
            'journal_id':self.journal_id.id,
            'move_type':'entry',
            'currency_id':self.currency_id.id,
            'posted_before':False,
            'partner_id':self.partner_id.id,
            'ref':"Comprobante de retencion iva de la factura nro "+self.invoice_id.invoice_number_next if self.invoice_id.invoice_number_next else self.invoice_number_next,
            })
        move_id=self.env['account.move'].create(vals)
        valores=({
            'account_id':account_cred_id,
            'credit':self.vat_retentioned,
            'currency_id':self.currency_id.id,
            'move_id':move_id.id,
            'balance':-1*self.vat_retentioned,
            'journal_id':self.journal_id.id,
            'partner_id':self.partner_id.id,
            })
        move_id.line_ids.create(valores)
        valores2=({
            'account_id':account_debi_id,
            'debit':self.vat_retentioned,
            'currency_id':self.currency_id.id,
            'move_id':move_id.id,
            'balance':self.vat_retentioned,
            'journal_id':self.journal_id.id,
            'partner_id':self.partner_id.id,
            })
        move_id.line_ids.create(valores2)
        move_id._post(soft=False)
        self.asiento_ret_iva_id=move_id.id



    def create_conciliacion_ret_iva(self):
        self.ensure_one()
        
        # 1. Determinar la cuenta contable de la conciliación
        if self.type in ('in_invoice', 'in_refund', 'in_receipt'):  # Proveedores
            # Usaremos la cuenta por pagar.
            account_id = self.partner_id.property_account_payable_id.id
            # En el asiento de la factura: El crédito es el saldo inicial (negativo en balance)
            # En el asiento de retención: El débito es el pago parcial (positivo en balance)
        elif self.type in ('out_invoice', 'out_refund', 'out_receipt'):  # Clientes
            # Usaremos la cuenta por cobrar.
            account_id = self.partner_id.property_account_receivable_id.id
            # En el asiento de la factura: El débito es el saldo inicial (positivo en balance)
            # En el asiento de retención: El crédito es el pago parcial (negativo en balance)
        else:
            return

        # 2. Buscar las líneas de apunte contable para la conciliación
        # Línea de la factura (cuenta por pagar/cobrar)
        invoice_lines = self.invoice_id.line_ids.filtered(lambda l: l.account_id.id == account_id and not l.reconciled and l.partner_id.id == self.partner_id.id)
        
        # Línea del asiento de retención (la contrapartida, que es la misma cuenta por pagar/cobrar)
        retention_move_lines = self.asiento_ret_iva_id.line_ids.filtered(lambda l: l.account_id.id == account_id and not l.reconciled and l.partner_id.id == self.partner_id.id)
        
        # 3. Conciliar las líneas. 
        # Si la suma de los balances no es cero, se debe crear una conciliación parcial.
        if invoice_lines and retention_move_lines:
            lines_to_reconcile = invoice_lines + retention_move_lines

            # Odoo puede intentar la conciliación si las líneas son abiertas. 
            # El error sugiere que Odoo no puede hacer el match automáticamente
            # si la suma de balance no es cero.
            
            # En lugar de solo .reconcile(), intentaremos crear un objeto de conciliación
            # si las líneas tienen saldo remanente (es una conciliación parcial)

            # Si el módulo 'account' tiene el método 'reconcile_partial', úsalo:
            if hasattr(lines_to_reconcile, 'reconcile'):
                lines_to_reconcile.reconcile()
            else:
                # Si .reconcile() falla, intentamos usar .partial_reconcile() si existe 
                # (aunque .reconcile() suele manejarlo)
                raise UserError("Error de conciliación: No se pudo conciliar el monto. Verifique que la cuenta contable de la factura y el asiento de retención sean la misma, y que la divisa coincida.")



    def create_conciliacion_ret_iva_org(self):
        factor=1
        if self.company_id.currency_id.id!=self.invoice_id.currency_id.id:
            factor=self.invoice_id.tasa
        ### para proveedores
        if self.type in ('in_invoice','in_refund','in_receipt'):
            cuenta_ref=self.partner_id.property_account_payable_id.id
            id_move_credit=self.env['account.move.line'].search([('move_id','=',self.invoice_id.id),('account_id','=',cuenta_ref)],limit=1)
            id_move_debit=self.env['account.move.line'].search([('move_id','=',self.asiento_ret_iva_id.id),('account_id','=',cuenta_ref)],limit=1)
        ### para clientes
        if self.type in ('out_invoice','out_refund','out_receipt'):
            cuenta_ref=self.partner_id.property_account_receivable_id.id
            id_move_credit=self.env['account.move.line'].search([('move_id','=',self.asiento_ret_iva_id.id),('account_id','=',cuenta_ref)],limit=1)
            id_move_debit=self.env['account.move.line'].search([('move_id','=',self.invoice_id.id),('account_id','=',cuenta_ref)],limit=1)
        monto=self.vat_retentioned
        value=({
            'debit_move_id':id_move_debit.id,
            'credit_move_id':id_move_credit.id,
            'amount':monto, # siempre va en bs
            'debit_amount_currency':monto/factor,
            'credit_amount_currency':monto/factor,
            'max_date':self.voucher_delivery_date,
            'credit_currency_id':3,
            'debit_currency_id':3,
            })
        self.env['account.partial.reconcile'].create(value)



    def action_draft(self):
        self.state='draft'
        self.asiento_ret_iva_id.with_context(force_delete=True).unlink()

    def asigna_nro_voicher(self):
        fecha = str(self.voucher_delivery_date)
        fecha_aux=fecha
        ano=fecha_aux[0:4]
        mes=fecha[5:7]
        resultado=ano+mes
        resultado=resultado+self.correlativo_voucher()
        return resultado

    def correlativo_voucher(self):

        self.ensure_one()
        
        company_id = self.env.company.id
        SEQUENCE_CODE = 'nro_voucher_ret_iva_'+str(company_id)
        IrSequence = self.env['ir.sequence'].with_context(force_company=company_id)
        name = IrSequence.next_by_code(SEQUENCE_CODE)

        # si aún no existe una secuencia para esta empresa, cree una
        if not name:
            IrSequence.sudo().create({
                #'prefix': 'RET_IVA/',
                'name': 'Localización Venezolana Nro vaucher IVA %s' % company_id,
                'code': SEQUENCE_CODE,
                'implementation': 'no_gap',
                'padding': 8,
                'number_increment': 1,
                'company_id': company_id,
            })
            name = IrSequence.next_by_code(SEQUENCE_CODE)
        return name

    def nro_asiento_comp_ret_iva(self):

        self.ensure_one()
        
        company_id = self.env.company.id
        SEQUENCE_CODE = 'nro_asiento_ret_iva_'+str(company_id)
        IrSequence = self.env['ir.sequence'].with_context(force_company=company_id)
        name = IrSequence.next_by_code(SEQUENCE_CODE)

        # si aún no existe una secuencia para esta empresa, cree una
        if not name:
            IrSequence.sudo().create({
                'prefix': 'RET_IVA/',
                'name': 'Localización Venezolana Nro asiento ret IVA %s' % company_id,
                'code': SEQUENCE_CODE,
                'implementation': 'no_gap',
                'padding': 8,
                'number_increment': 1,
                'company_id': company_id,
            })
            name = IrSequence.next_by_code(SEQUENCE_CODE)
        return name

    @api.depends('retention_line_ids')
    def _compute_base_imponible(self):
        for selff in self:
            base=0
            if selff.retention_line_ids:
                for line in selff.retention_line_ids:
                    base=base+line.amount_vat_ret
            selff.amount_untaxed=base


    @api.depends('retention_line_ids')
    def _compute_vat_retentioned(self):
        for selff in self:
            retentioned=0
            if selff.retention_line_ids:
                for line in selff.retention_line_ids:
                    retentioned=retentioned+line.retention_amount
            selff.vat_retentioned=retentioned

    def float_format2(self,valor):
        #valor=self.base_tax
        if valor:
            result = '{:,.2f}'.format(valor)
            result = result.replace(',','*')
            result = result.replace('.',',')
            result = result.replace('*','.')
        else:
            result = "0,00"
        return result

    def periodo(self):
        fecha = str(self.voucher_delivery_date)
        fecha_aux=fecha
        ano=fecha_aux[0:4]
        mes=fecha[5:7]
        dia=fecha[8:10]  
        resultado="Año: "+ano+" Mes: "+mes
        return resultado

    def formato_fecha2(self):
        fecha = str(self.voucher_delivery_date)
        fecha_aux=fecha
        ano=fecha_aux[0:4]
        mes=fecha[5:7]
        dia=fecha[8:10]  
        resultado=dia+"/"+mes+"/"+ano
        return resultado

    def doc_cedula(self,aux):
        #nro_doc=self.partner_id.vat
        busca_partner = self.env['res.partner'].search([('id','=',aux)])
        for det in busca_partner:
            tipo_doc=busca_partner.doc_type
            nro_doc=str(busca_partner.vat)
        nro_doc=nro_doc.replace('V','')
        nro_doc=nro_doc.replace('v','')
        nro_doc=nro_doc.replace('E','')
        nro_doc=nro_doc.replace('e','')
        nro_doc=nro_doc.replace('G','')
        nro_doc=nro_doc.replace('g','')
        nro_doc=nro_doc.replace('J','')
        nro_doc=nro_doc.replace('j','')
        nro_doc=nro_doc.replace('P','')
        nro_doc=nro_doc.replace('p','')
        nro_doc=nro_doc.replace('-','')
        
        if tipo_doc=="v":
            tipo_doc="V"
        if tipo_doc=="e":
            tipo_doc="E"
        if tipo_doc=="g":
            tipo_doc="G"
        if tipo_doc=="j":
            tipo_doc="J"
        if tipo_doc=="p":
            tipo_doc="P"
        resultado=str(tipo_doc)+"-"+str(nro_doc)
        return resultado





    def comprobante(self):
        return self.env.ref('iva_retention.action_iva_ret_report').report_action(self)

class VatRetentionInvoiceLine(models.Model):
    """This model is for a line invoices withholed."""
    _name = 'vat.retention.invoice.line'

    name = fields.Char(string='Description')
    retention_id = fields.Many2one('vat.retention', string='Retención de IVA',ondelete="cascade")
    amount_untaxed = fields.Float(string='Cantidad sin Impuestos')
    amount_vat_ret = fields.Float(string='Importe del Impuesto')
    retention_amount = fields.Float(string='Retención',compute='_cal_retention_amount',store=True)

    invoice_number = fields.Char(string='Invoice number')
    retention_rate = fields.Float(string='Tasa de Retención', help="The retention rate can vary between 75% al 100% depending on the taxpayer.")
    invoice_id = fields.Many2one('account.move', string='Invoice', ondelete='restrict', help="Retention invoice")
    currency_id = fields.Many2one('res.currency', string='Currency',default=lambda self: self.env.company.currency_id.id)
    base_imponible = fields.Float()
    #tax_line_ids = fields.One2many('vat.retention.tax.lines', 'vat_ret_line_id', string='tax lines')
    #campo por agregar
    # tax_book_id = fields.Many2one('tax.book', string="Tax book")

    # campos a ser eliminados
    tax_id = fields.Many2one('account.tax', string='Tax')

    #@api.onchange('amount_vat_ret','retention_rate')
    @api.depends('amount_vat_ret','retention_rate')
    def _cal_retention_amount(self):
        for selff in self:
            result=0
            result=selff.amount_vat_ret*selff.retention_rate/100
            selff.retention_amount=result

    def float_format(self,valor):
        #valor=self.base_tax
        if valor:
            result = '{:,.2f}'.format(valor)
            result = result.replace(',','*')
            result = result.replace('.',',')
            result = result.replace('*','.')
        else:
            result = "0,00"
        return result

    def formato_fecha(self):
        fecha = str(self.invoice_id.invoice_date)
        fecha_aux=fecha
        ano=fecha_aux[0:4]
        mes=fecha[5:7]
        dia=fecha[8:10]  
        resultado=dia+"/"+mes+"/"+ano
        return resultado

    def valida_excento(self):
        valor = 0
        factor=1
        if self.invoice_id.currency_id.id!=self.retention_id.company_id.currency_id.id:
            factor=self.invoice_id.tasa
        for line in self.invoice_id.invoice_line_ids:
            if line.tax_ids.aliquot=='exempt':
                valor = valor + line.price_subtotal*factor
        return valor