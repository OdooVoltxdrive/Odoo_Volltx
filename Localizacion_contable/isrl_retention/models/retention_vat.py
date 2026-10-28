# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta

_logger = logging.getLogger('__name__')


class ProductTemplate(models.Model):
    _inherit = 'product.template'
    concept_isrl_id = fields.Many2one('islr.concept', string='ISLR Concept')


class InvoiceLineInherit(models.Model):
    _inherit = 'account.move.line'

    concept_isrl_id = fields.Many2one(related='product_id.product_tmpl_id.concept_isrl_id', string='ISLR Concepto')
    vat_isrl_line_id = fields.Many2one('isrl.retention.invoice.line', string='ISLR Line')


class VatRetentionInvoiceLine(models.Model):
    """This model is for a line invoices withholed."""
    _name = 'isrl.retention.invoice.line'

    name = fields.Many2one('islr.concept', string='ISLR Concept')
    code = fields.Char( string='Código')
    retention_id = fields.Many2one('isrl.retention', string='Vat retention')
    cantidad = fields.Float(string='Cantidad Porcentual')
    base = fields.Float(string='Base')
    retention = fields.Float(string='Retención')
    sustraendo = fields.Float(string='Sustraendo')
    total = fields.Float(string='ISLR Amount retention')
    
class RetentionVat(models.Model):
    """This is a main model for rentetion vat control."""
    _name = 'isrl.retention'
    _inherit = ['mail.thread', 'mail.activity.mixin']



    name = fields.Char(string='Comprobante  Número', default='0000-00-00')
    move_id = fields.Many2one('account.move', string='Asiento Contable')
    
    invoice_id = fields.Many2one(comodel_name='account.move', string='Factura')
    #type = fields.Char(related='invoice_id.move_type')
    type = fields.Char()
    
    date_move = fields.Date(string='Date Move')
    date_isrl= fields.Date(string='Date ISLR')
    partner_id = fields.Many2one(comodel_name='res.partner', string='Empresa')
    
    lines_id = fields.One2many(comodel_name='isrl.retention.invoice.line', inverse_name='retention_id', string='Lines')
    
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done'),], string='State', readonly=True, default='draft')
    invoice_number=fields.Char(string='Nro de Factura')
    company_id = fields.Many2one('res.company',default=lambda self: self.env.company)


    def comprobante(self):
        return self.env.ref('isrl_retention.action_islr_ret_report').report_action(self)




    def _factura_prov_cli(self):
        self.invoice_number="...."
        """factura= self.env['account.move'].search([('id','=',self.invoice_id.id)])
        for det in factura:
            invoice_number=det.invoice_number
        self.invoice_number= invoice_number"""


    def rif_ced(self,part_id):
        resultado='----'
        busca_partner = self.env['res.partner'].search([('id','=',part_id)],limit=1)
        if busca_partner:
            if busca_partner.vat:
                resultado=str(busca_partner.vat)
        return resultado


    def doc_cedula(self,aux):
        #nro_doc=self.partner_id.vat
        busca_partner = self.env['res.partner'].search([('id','=',aux)])
        for det in busca_partner:
            nro_doc=str(busca_partner.vat)
        resultado=str(nro_doc)
        return resultado
        #raise UserError(_('cedula: %s')%resultado)
        
    def action_post(self):
        self.ejecuta()



    def ejecuta(self):
        #raise UserError(_('moneda compañia'))
        customer = ('out_invoice','out_refund','out_receipt')
        vendor   = ('in_invoice','in_refund','in_receipt')
        #name_asiento = self.env['ir.sequence'].next_by_code('purchase.isrl.retention.account')

        self.state =  'done' #'done' 
        if self.invoice_id.move_type in vendor:
            if not self.invoice_id.isrl_ret_aux_id:
                self.name=self.env['ir.sequence'].next_by_code('purchase.isrl.retention.voucher.number')
            else:
                self.name=self.invoice_id.isrl_ret_aux_id
        else:
            cant=len(self.name)
            if cant!=14:
                raise UserError(_('El Número del comprobante debe tener 14 digitos'))
            else:
                pass
        ##self.move_id.action_post() # DARRELL
        name_asiento = self.env['ir.sequence'].next_by_code('purchase.isrl.retention.account')
        id_move=self.registro_movimiento_retencion(name_asiento)
        idv_move=id_move.id
        valor=self.registro_movimiento_linea_retencion(idv_move,name_asiento)
        moves= self.env['account.move'].search([('id','=',idv_move)])
        moves._post(soft=False)
        self.move_id=id_move.id
        ##moves.filtered(lambda move: move.journal_id.post_at != 'bank_rec').post()

    def total_ret(self):
        total_retenido=self.vat_retentioned
        return total_retenido


    def conv_div_extranjera(self,valor):
        self.invoice_id.currency_id.id
        fecha_contable_doc=self.invoice_id.date
        monto_factura=self.invoice_id.amount_total
        valor_aux=0
        #raise UserError(_('moneda compañia: %s')%self.company_id.currency_id.id)
        if self.invoice_id.currency_id.id!=self.invoice_id.company_id.currency_id.id:
            rate=self.invoice_id.tasa  # LANTA
            #rate=round(valor_aux,2)  # ODOO SH
            resultado=valor/rate
        else:
            resultado=valor
        return resultado

    def registro_movimiento_retencion(self,consecutivo_asiento):
        #raise UserError(_('darrell = %s')%self.partner_id.vat_retention_rate)
        name = consecutivo_asiento
        signed_amount_total=0
        #amount_itf = round(float(total_monto) * float((igtf_porcentage / 100.00)),2)
        if self.invoice_id.move_type=="in_invoice" or self.invoice_id.move_type=="in_receipt":
            signed_amount_total=self.total_ret() #self.conv_div_extranjera(self.total_ret()) #self.vat_retentioned
        if self.type=="out_invoice" or self.type=="out_receipt":
            signed_amount_total=-1*self.total_ret() #self.conv_div_extranjera(self.total_ret()) #(-1*self.vat_retentioned)

        if self.invoice_id.move_type=="out_invoice" or self.invoice_id.move_type=="out_refund" or self.invoice_id.move_type=="out_receipt":
            id_journal=self.partner_id.sale_isrl_id.id
            name_retenido=self.invoice_id.company_id.partner_id.name
            #rate_valor=self.partner_id.vat_retention_rate
        if self.invoice_id.move_type=="in_invoice" or self.invoice_id.move_type=="in_refund" or self.invoice_id.move_type=="in_receipt":
            """if self.invoice_id.company_id.confg_ret_proveedores=="c":
                id_journal=self.invoice_id.company_id.partner_id.sale_isrl_id.id
                name_retenido=self.partner_id.name
            if self.invoice_id.company_id.confg_ret_proveedores=="p":"""
            id_journal=self.partner_id.sale_isrl_id.id
            name_retenido=self.invoice_id.company_id.partner_id.name

            #rate_valor=self.company_id.partner_id.vat_retention_rate
        #raise UserError(_('papa = %s')%signed_amount_total)
        value = {
            'name': name,
            'date': self.invoice_id.date,#listo
            #'amount_total':self.vat_retentioned,# LISTO
            'partner_id': self.partner_id.id, #LISTO
            'journal_id':id_journal,
            'ref': "Retención del %s %% ISLR de la Factura %s" % (name_retenido,self.invoice_id.name),
            #'amount_total':self.vat_retentioned,# LISTO
            #'amount_total_signed':signed_amount_total,# LISTO
            'move_type': "entry",# estte campo es el que te deja cambiar y almacenar valores
            'isrl_ret_id': self.id,
        }
        #raise UserError(_('value= %s')%value)
        move_obj = self.env['account.move']
        move_id = move_obj.create(value)    
        #raise UserError(_('move_id= %s')%move_id) 
        return move_id

    def registro_movimiento_linea_retencion(self,id_movv,consecutivo_asiento):
        #raise UserError(_('ID MOVE = %s')%id_movv)
        name = consecutivo_asiento
        valores = self.total_ret() #self.conv_div_extranjera(self.total_ret()) #self.vat_retentioned #VALIDAR CONDICION
        cero = 0.0
        #raise UserError(_('valores = %s')%valores)
        if self.invoice_id.move_type=="out_invoice" or self.invoice_id.move_type=="out_refund" or self.invoice_id.move_type=="out_receipt":
            cuenta_ret_cliente=self.partner_id.account_isrl_receivable_id.id# cuenta retencion cliente
            cuenta_ret_proveedor=self.partner_id.account_isrl_payable_id.id#cuenta retencion proveedores
            cuenta_clien_cobrar=self.partner_id.property_account_receivable_id.id
            cuenta_prove_pagar = self.partner_id.property_account_payable_id.id
            name_retenido=self.invoice_id.company_id.partner_id.name
            #rate_valor=self.partner_id.vat_retention_rate
        if self.type=="in_invoice" or self.type=="in_refund" or self.type=="in_receipt":
            """if self.invoice_id.company_id.confg_ret_proveedores=="c":
                cuenta_ret_cliente=self.invoice_id.company_id.partner_id.account_isrl_receivable_id.id# cuenta retencion cliente
                cuenta_ret_proveedor=self.invoice_id.company_id.partner_id.account_isrl_payable_id.id#cuenta retencion proveedores
                cuenta_clien_cobrar=self.invoice_id.company_id.partner_id.property_account_receivable_id.id
                cuenta_prove_pagar = self.invoice_id.company_id.partner_id.property_account_payable_id.id
            if self.invoice_id.company_id.confg_ret_proveedores=="p":"""
            cuenta_ret_cliente=self.partner_id.account_isrl_receivable_id.id# cuenta retencion cliente
            cuenta_ret_proveedor=self.partner_id.account_isrl_payable_id.id#cuenta retencion proveedores
            cuenta_clien_cobrar=self.partner_id.property_account_receivable_id.id
            cuenta_prove_pagar = self.partner_id.property_account_payable_id.id
            name_retenido=self.partner_id.name
            #rate_valor=self.company_id.partner_id.vat_retention_rate

        tipo_empresa=self.invoice_id.move_type
        #raise UserError(_('papa = %s')%tipo_empresa)
        if tipo_empresa=="in_invoice" or tipo_empresa=="in_receipt":#aqui si la empresa es un proveedor
            cuenta_haber=cuenta_ret_proveedor
            cuenta_debe=cuenta_prove_pagar            
            balance_a=cero-valores
            balance_b=valores-cero

        if tipo_empresa=="in_refund":
            cuenta_haber=cuenta_prove_pagar
            cuenta_debe=cuenta_ret_proveedor
            balance_a=cero-valores
            balance_b=valores-cero

        if tipo_empresa=="out_invoice" or tipo_empresa=="out_receipt":# aqui si la empresa es cliente
            cuenta_haber=cuenta_clien_cobrar
            cuenta_debe=cuenta_ret_cliente
            balance_a=valores-cero
            balance_b=cero-valores

        if tipo_empresa=="out_refund":
            cuenta_haber=cuenta_ret_cliente
            cuenta_debe=cuenta_clien_cobrar
            balance_a=valores-cero
            balance_b=cero-valores
        #balances=cero-valores
        balances=balance_a
        value = {
             'name': name,
             'ref' : "Retención del %s %% ISLR de la Factura %s" % (name_retenido,self.move_id.name),
             'move_id': int(id_movv),
             'date': self.move_id.date,
             'partner_id': self.partner_id.id,
             'account_id': cuenta_haber,
             #'amount_currency': 0.0,
             #'date_maturity': False,
             'credit': valores,
             'debit': 0.0, # aqi va cero   EL DEBITO CUNDO TIENE VALOR, ES QUE EN ACCOUNT_MOVE TOMA UN VALOR
             'balance':-valores, # signo negativo
             'price_unit':balances,
             'price_subtotal':balances,
             'price_total':balances,

        }
        move_line_obj = self.env['account.move.line']
        move_line_id1 = move_line_obj.create(value)

        #balances=valores-cero
        balances=balance_b
        value['account_id'] = cuenta_debe
        value['credit'] = 0.0 # aqui va cero
        value['debit'] = valores
        value['balance'] = valores
        value['price_unit'] = balances
        value['price_subtotal'] = balances
        value['price_total'] = balances
        value['partner_id'] = self.partner_id.id

        move_line_id2 = move_line_obj.create(value)
    
    def formato_fecha2(self,date):
        fecha = str(date)
        fecha_aux=fecha
        ano=fecha_aux[0:4]
        mes=fecha[5:7]
        dia=fecha[8:10]  
        resultado=dia+"/"+mes+"/"+ano
        return resultado

    def float_format(self,valor):
        #valor=self.base_tax
        if valor:
            result = '{:,.2f}'.format(valor)
            result = result.replace(',','*')
            result = result.replace('.',',')
            result = result.replace('*','.')
        else:
            result="0,00"
        return result
    def get_address_partner(self):
        location = ''
        streets = ''
        if self.partner_id:
            location = self._get_state_and_city()
            streets = self._get_streets()
        return (streets + " " + location)


    def _get_state_and_city(self):
        state = ''
        city = ''
        if self.partner_id.state_id:
            state = "Edo." + " " + str(self.partner_id.state_id.name or '')
            _logger.info("\n\n\n state %s \n\n\n", state)
        if self.partner_id.city:
            city = str(self.partner_id.city or '')
            # _logger.info("\n\n\n city %s\n\n\n", city)
        result = city + " " + state
        _logger.info("\n\n\n result %s \n\n\n", result)
        return  result 


    def _get_streets(self):
        street2 = ''
        av = ''
        if self.partner_id.street:
            av = str(self.partner_id.street or '')
        if self.partner_id.street2:
            street2 = str(self.partner_id.street2 or '')
        result = av + " " + street2
        return result

    def get_company_address(self):
        location = ''
        streets = ''
        if self.invoice_id.company_id:
            streets = self._get_company_street()
            location = self._get_company_state_city()
        _logger.info("\n\n\n street %s location %s\n\n\n", streets, location)
        return  (streets + " " + location)


    def _get_company_street(self):
        street2 = ''
        av = ''
        if self.invoice_id.company_id.street:
            av = str(self.invoice_id.company_id.street or '')
        if self.invoice_id.company_id.street2:
            street2 = str(self.invoice_id.company_id.street2 or '')
        result = av + " " + street2
        return result


    def _get_company_state_city(self):
        state = ''
        city = ''
        if self.invoice_id.company_id.state_id:
            state = "Edo." + " " + str(self.invoice_id.company_id.state_id.name or '')
            _logger.info("\n\n\n state %s \n\n\n", state)
        if self.invoice_id.company_id.city:
            city = str(self.invoice_id.company_id.city or '')
            _logger.info("\n\n\n city %s\n\n\n", city)
        result = city + " " + state
        _logger.info("\n\n\n result %s \n\n\n", result)
        return  result

    @api.model
    def _compute_amount_untaxed(self):
        for item in self:
            item.amount_untaxed = 0 
            for line in item.lines_id:
                item.amount_untaxed += line.base

    @api.model
    def _compute_vat_retentioned(self):
        for item in self :
            item.vat_retentioned = 0 
            for line in item.lines_id :
                item.vat_retentioned += line.total
                #item.vat_retentioned += line.total

    amount_untaxed = fields.Float(string='Base Imponible',compute='_compute_amount_untaxed')
    #vat_retentioned = fields.Float(string='ISLRretenido')
    vat_retentioned = fields.Float(string='ISLRretenido',compute='_compute_vat_retentioned')