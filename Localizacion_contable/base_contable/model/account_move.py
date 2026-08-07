# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError, AccessError
from odoo.tools import float_compare, date_utils
from odoo.tools.misc import formatLang, format_date
from contextlib import ExitStack, contextmanager

from datetime import date, timedelta, datetime
from collections import defaultdict
from itertools import zip_longest
from hashlib import sha256
from json import dumps

from odoo.tools import (
    date_utils,
    float_compare,
    float_is_zero,
    float_repr,
    format_amount,
    format_date,
    formatLang,
    frozendict,
    get_lang,
    index_exists,
    is_html_empty,
)

import ast
import json
import re
import warnings
import pytz

#forbidden fields
INTEGRITY_HASH_MOVE_FIELDS = ('date', 'journal_id', 'company_id')
INTEGRITY_HASH_LINE_FIELDS = ('debit', 'credit', 'account_id', 'partner_id')
#_logger = logging.getLogger('__name__')



class AccountMove(models.Model):
    _inherit = 'account.move'

    invoice_number_next = fields.Char(string='Nro Invoice', copy=False, tracking=True)
    invoice_number_control = fields.Char(string='Nro Control', copy=False, tracking=True)
    invoice_number_unique = fields.Char(string='Nro Control Unique', copy=False, tracking=True)
    delivery_note_next_number = fields.Char(string='Nro. Nota de Entrega',tracking=True)
    is_delivery_note = fields.Boolean(default=False, tracking=True)
    is_manual = fields.Boolean(string='Numeracion Manual', tracking=True, compute='_compute_is_manual',store=True)
    hide_book = fields.Boolean(string='Excluir de Libros', tracking=True, default=False)
    reason = fields.Char('Referencia de Factura')
    tasa = fields.Float(compute='_compute_tasa',store=True, readonly=True,digits=(12, 4))
    hora_public = fields.Char()
    #is_branch_office = fields.Boolean(string='Tiene sucursal', tracking=True)
    nro_planilla_exportacion = fields.Char()
    image = fields.Binary(string='imagen', store=True, attachment=True)
    file_name = fields.Char('Filename')

    nro_form_impor = fields.Char()
    nro_expe_impor = fields.Char()
    operation_type = fields.Selection([
        ('national','Nacional'),
        ('international','Internacional'),
    ],default='national')
    price_ref_div_product=fields.Boolean(string='Usar precio indexado USD del producto?',default=lambda self: self.env.company.price_ref_div_product,help='Este campo si es verdadero, usa el precio de venta fijado en divisa y lo lleva a Bs según la tasa Fijada')
    #price_ref_div_product=fields.Boolean(string='Usar precio indexado USD del producto?',default=False,help='Este campo si es verdadero, usa el precio de venta fijado en divisa y lo lleva a Bs según la tasa Fijada')
    amount_total_signed_div = fields.Float(compute='_compute_total_div')
    amount_untaxed_loc_ve = fields.Monetary(compute='_compute_amunt_untaxed_ve')
    ########################### para la vista del igtf #############
    cond_fact = fields.Selection([('cont','Contado'),('cred','Credito')],default="cred")
    amount_base_imponible=fields.Monetary(compute='_compute_base_imponible')
    amount_exento=fields.Monetary(compute='_compute_exemto')
    amount_ivag = fields.Monetary(compute='_compute_aliquot_general')
    amount_ivar = fields.Monetary(compute='_compute_aliquot_reducida')
    amount_ivaa = fields.Monetary(compute='_compute_aliquot_adicional')
    amount_igtf = fields.Monetary(compute='_compute_igtf')
    amount_igtf_signed = fields.Float()
    igtf_ids=fields.One2many('account.payment.fact','move_id', string='Cobros IGTF')
    amount_total_aux = fields.Float(compute='_compute_total_aux')
    observacion = fields.Char()
    fact_afect = fields.Char()

    #show_update_fpos = fields.Boolean(string="Has Fiscal Position Changed", store=False)  
    # --- NUEVO MÉTODO DE AUDITORÍA ---
    def _log_and_raise_fiscal_error(self, message, event_type='cancel_attempt'):
        """Registra el evento en l10n.ve.fiscal.log y lanza error."""
        self.env['l10n.ve.fiscal.log'].create({
            'model_name': 'account.move',
            'res_id': self.id,
            'event_type': event_type,
            'description': message,
            'document_ref': f'account.move,{self.id}',
        })
        self.env.cr.commit() # Asegura que el log se guarde antes del rollback
        raise UserError(_(message))


    @api.depends('move_type')
    def _compute_is_manual(self):
        for move in self:
            # Facturas de cliente: out_invoice, out_refund, out_receipt
            if move.move_type in ('out_invoice', 'out_refund', 'out_receipt'):
                move.is_manual = False
            # Facturas de proveedor: in_invoice, in_refund, in_receipt
            elif move.move_type in ('in_invoice', 'in_refund', 'in_receipt'):
                move.is_manual = True
            else:
                move.is_manual = False


    def _compute_amunt_untaxed_ve(self):
        for selff in self:
            selff.amount_untaxed_loc_ve=abs(selff.amount_base_imponible+selff.amount_exento)


    def _compute_base_imponible(self):
        # Itera sobre las facturas
        for move in self:
            total_imponible = 0
            
            # Itera sobre las líneas de la factura
            for det in move.invoice_line_ids:
                # 1. Bandera para determinar si la línea es imponible
                es_imponible = False
                
                # 2. Itera sobre CADA IMPUESTO en el Many2many
                for tax in det.tax_ids:
                    # 3. Si encuentra AL MENOS UN impuesto que NO sea 'exempt', la línea es imponible
                    if tax.aliquot != 'exempt':
                        es_imponible = True
                        break  # Sale del bucle de impuestos, ya que encontramos uno no exento
                
                # 4. Suma el subtotal si la línea es imponible
                if es_imponible:
                    total_imponible += det.price_subtotal
            
            move.amount_base_imponible = total_imponible


#aqui
    def _compute_exemto(self):
        for move in self:
            total_exento = monto_igtf = 0
            
            for det in move.invoice_line_ids:
                # 1. Bandera para determinar si TODOS los impuestos son exentos
                es_totalmente_exento = False

                # Verificamos si la línea está marcada como exenta por el campo personalizado
                if det.linea_exenta:
                    # Si el campo personalizado marca la línea como exenta, se suma.
                    monto_igtf+=det.price_subtotal
                    es_totalmente_exento = True
                
                # Si el campo personalizado NO la marca como exenta, revisamos los impuestos
                elif det.tax_ids:
                    # Verifica si CADA impuesto en el Many2many es 'exempt'
                    if all(tax.aliquot == 'exempt' for tax in det.tax_ids):
                        # Si todos los impuestos son 'exempt', la línea es exenta.
                        es_totalmente_exento = True

                # 2. Si la línea se califica como exenta, sumamos su subtotal
                if es_totalmente_exento:
                    total_exento += det.price_subtotal

            move.amount_exento = total_exento-monto_igtf



    def _compute_aliquot_general(self):
        for move in self:
            total_general = 0
            porcentage=0
            
            for det in move.invoice_line_ids:
                # 1. Bandera para determinar si TODOS los impuestos son exentos
                es_totalmente_general = False

                # Verificamos si la línea está marcada como exenta por el campo personalizado
                if det.linea_exenta:
                    # Si el campo personalizado marca la línea como exenta, se suma.
                    es_totalmente_exento = True
                
                # Si el campo personalizado NO la marca como exenta, revisamos los impuestos
                elif det.tax_ids:
                    # Verifica si CADA impuesto en el Many2many es 'exempt'
                    if all(tax.aliquot == 'general' for tax in det.tax_ids):
                        # Si todos los impuestos son 'general', la línea es general.
                        es_totalmente_general = True
                        porcentage=det.tax_ids.amount

                # 2. Si la línea se califica como exenta, sumamos su subtotal
                if es_totalmente_general:
                    total_general += det.price_subtotal

            move.amount_ivag = round(total_general*porcentage/100,4)


    def _compute_aliquot_reducida(self):
        for move in self:
            total_reducida = 0
            porcentage=0
            
            for det in move.invoice_line_ids:
                # 1. Bandera para determinar si TODOS los impuestos son exentos
                es_totalmente_reducida = False

                # Verificamos si la línea está marcada como exenta por el campo personalizado
                if det.linea_exenta:
                    # Si el campo personalizado marca la línea como exenta, se suma.
                    es_totalmente_exento = True
                
                # Si el campo personalizado NO la marca como exenta, revisamos los impuestos
                elif det.tax_ids:
                    # Verifica si CADA impuesto en el Many2many es 'exempt'
                    if all(tax.aliquot == 'reduced' for tax in det.tax_ids):
                        # Si todos los impuestos son 'general', la línea es general.
                        es_totalmente_reducida = True
                        porcentage=det.tax_ids.amount

                # 2. Si la línea se califica como exenta, sumamos su subtotal
                if es_totalmente_reducida:
                    total_reducida += det.price_subtotal

            move.amount_ivar = round(total_reducida*porcentage/100,4)


    def _compute_aliquot_adicional(self):
        for move in self:
            total_adicional = 0
            porcentage=0
            
            for det in move.invoice_line_ids:
                # 1. Bandera para determinar si TODOS los impuestos son exentos
                es_totalmente_adicional = False

                # Verificamos si la línea está marcada como exenta por el campo personalizado
                if det.linea_exenta:
                    # Si el campo personalizado marca la línea como exenta, se suma.
                    es_totalmente_exento = True
                
                # Si el campo personalizado NO la marca como exenta, revisamos los impuestos
                elif det.tax_ids:
                    # Verifica si CADA impuesto en el Many2many es 'exempt'
                    if all(tax.aliquot == 'additional' for tax in det.tax_ids):
                        # Si todos los impuestos son 'general', la línea es general.
                        es_totalmente_adicional = True
                        porcentage=det.tax_ids.amount

                # 2. Si la línea se califica como exenta, sumamos su subtotal
                if es_totalmente_adicional:
                    total_adicional += det.price_subtotal

            move.amount_ivaa = round(total_adicional*porcentage/100,4)




    def _compute_igtf(self):
        valor=0
        if self.igtf_ids:
            for item in self.igtf_ids:
                valor=valor+item.monto_ret_bs
        if not self.igtf_ids and self.cond_fact=='cred' and self.company_id.currency_id.id!=self.currency_id.id:
            total_fact=self.amount_base_imponible+self.amount_exento+self.amount_ivag+self.amount_ivar+self.amount_ivaa
            valor=(total_fact*self.company_id.percentage_cli_igtf/100)*self.tasa
        if self.company_id.currency_id.id!=self.currency_id.id:
            valor=valor/self.tasa
        self.amount_igtf=valor

    def _compute_total_aux(self):
        self.amount_total_aux=self.amount_total+self.amount_igtf

    def pago_prog(self):
        return self.env['wizard.payment.fact']\
            .with_context(active_ids=self.ids, active_model='account.move', active_id=self.id)\
            .action_register_ext_payment()




    def _compute_total_div(self):
        for selff in self:
            selff.amount_total_signed_div=selff.amount_total_signed/selff.tasa if selff.tasa!=0 else selff.amount_total_signed

    @api.onchange('partner_id')
    def function_operation_type(self):
        for selff in self:
            selff.operation_type=selff.partner_id.partner_type



    @api.depends('invoice_date','date')
    @api.onchange('invoice_date','date')
    def _compute_tasa(self):
        result=1
        for selff in self:
            if selff.invoice_date:
                lista=selff.env['res.currency.rate'].search([('currency_id','=',selff.company_id.currency_sec_id.id),('name','<=',selff.invoice_date)],order='name desc',limit=1)
            else:
                lista=selff.env['res.currency.rate'].search([('currency_id','=',selff.company_id.currency_sec_id.id),('name','<=',selff.date)],order='name desc',limit=1)
            if lista:
                result=lista.inverse_company_rate
            selff.tasa=result



    @api.onchange('journal_id')
    def function_nota_entrega(self):
        if self.journal_id.nota_entrega==True:
            self.is_delivery_note=True
            self.hide_book=True
        else:
            self.is_delivery_note=False
            self.hide_book=False

    @api.onchange('move_type')
    def _onchange_default_manual(self):
        if self.move_type in ['in_invoice', 'in_refund','in_receipt']:
            self.is_manual = True

    def action_post(self):
        for selff in self:
            if selff.move_type!='entry':
                selff._validate_product_prices()
                selff._validate_product_taxes()
                selff.inserta_igtf()
            res=super().action_post()
            if selff.move_type!='entry':
                selff.valida_pagos_progra()
                selff.asig_nro_fact_control()
            selff.hora_public=  self.get_local_time()  #datetime.now().strftime('%H-4:%M:%S')   #datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            #raise UserError(_('move xx = %s ')%self)
            return res



    def _validate_product_prices(self):
        """ Valida que el precio unitario de las líneas de producto sea positivo. """
        for move in self:
            # Solo aplica a facturas de venta o compra
            if move.move_type in ('out_invoice', 'in_invoice', 'out_refund', 'in_refund'):
                
                # Buscamos líneas que son productos y tienen precio unitario <= 0
                lines_with_zero_or_negative_price = move.invoice_line_ids.filtered(
                    lambda line: line.product_id and line.price_subtotal <= 0
                )
                
                if lines_with_zero_or_negative_price:
                    # Construimos un mensaje de error detallado
                    product_names = ', '.join(lines_with_zero_or_negative_price.mapped('product_id.display_name'))
                    #move._log_and_raise_fiscal_error("🛑 Productos con precio cero/negativo: %s" % product_names)
                    raise UserError(_(
                        "🛑 No se puede publicar la factura."
                        "\nLos siguientes productos tienen un Precio (cero o negativo) o un descuento del 100 porciento:"
                        "\n%s"
                        "\n\nPor favor, corrija los precios o descuentos e intente publicar de nuevo."
                    ) % product_names)


    def _validate_product_taxes(self):
        """ Valida que todas las líneas de productos en la factura tengan al menos un impuesto. """
        for move in self:
            # Esta validación solo aplica a facturas de venta o compra (no asientos contables puros)
            if move.move_type in ('out_invoice', 'in_invoice','out_refund', 'in_refund','out_receipt','in_receipt'):
                # Buscamos líneas que sean productos (y no líneas contables puras) y que no tengan impuestos
                lines_without_tax = move.invoice_line_ids.filtered(
                    lambda line: line.product_id and not line.tax_ids
                )
                if lines_without_tax:
                    # Construimos un mensaje de error detallado
                    product_names = ', '.join(lines_without_tax.mapped('product_id.display_name'))
                    raise UserError(_(
                        "🛑 No se puede publicar la factura."
                        "\nLos siguientes productos no tienen impuestos asignados en sus líneas:"
                        "\n%s"
                        "\n\nPor favor, asigne un impuesto (o alícuota) a cada producto relevante e intente de nuevo."
                    ) % product_names)


    def get_local_time(self):

        # Obtener la hora actual en UTC y convertirla a la zona horaria local
        utc_now = datetime.now(pytz.utc)
        local_tz = pytz.timezone('America/Caracas') # Cambia esto a tu zona horaria
        local_time = utc_now.astimezone(local_tz)
        return local_time.strftime('%H:%M:%S') # Solo la hora


    def inserta_igtf(self):
        if self.amount_igtf!=0:
            if self.move_type in ('out_invoice','out_receipt','out_refund'):
                type_tax_use='sale'
            if self.move_type in ('in_invoice','in_receipt','in_refund'):
                type_tax_use='purchase'
            tax_ids=self.env['account.tax'].search([('aliquot','=','exempt'),('type_tax_use','=',type_tax_use),('company_id','=',self.company_id.id)],limit=1)
            if self.amount_igtf!=0:
                if not self.env.company.account_igtf_id.id:
                    raise UserError(_('No hay una cuanta contable para el igtf. Vaya a compañia y asigne una.'))
                vals=({
                    'name':"Registro de IGTF",
                    'quantity':1,
                    'price_unit':self.amount_igtf,
                    'tax_ids':tax_ids if tax_ids else '',
                    'move_id':self.id,
                    'account_id':self.env.company.account_igtf_id.id,
                    'linea_exenta':True,
                    })
                id_line2=self.invoice_line_ids.create(vals)

    def asig_nro_fact_control(self):
        if self.move_type!='entry':
            if self.is_delivery_note:
                if not self.delivery_note_next_number:
                    self.delivery_note_next_number = self.get_nro_nota_entrega()
                self.name=self.journal_id.code+ "/" + self.delivery_note_next_number
                self.payment_reference=self.journal_id.code+ "/" + self.delivery_note_next_number
            else:
                self.invoice_number_seq()
                self.invoice_control()
                if self.move_type in ('in_invoice','in_refund','in_receipt'):
                    # proveedor
                    pass
                    #self.name= self.name+'//'+str(self.invoice_number_next)
                    #self.name= self.invoice_number_next
                if self.move_type in ('out_invoice','out_refund','out_receipt'):
                    # cliente
                    self.name= self.journal_id.code + "/" +self.invoice_number_next
            for det_line_asiento in self.line_ids:
                if det_line_asiento.account_id.account_type in ('asset_receivable','liability_payable'):
                    det_line_asiento.name = self.journal_id.code + "/" + self.delivery_note_next_number if self.delivery_note_next_number else self.journal_id.code + "/" +self.invoice_number_next

    def valida_pagos_progra(self):
        # ELIMINAMOS la restricción que evitaba las Notas de Crédito (refund)
        if self.cond_fact == 'cont': 
            payments_to_process = self.igtf_ids.search([('move_id', '=', self.id)])
            if not payments_to_process:
                # Opcional: Para Notas de Crédito podrías querer que esto no sea obligatorio
                if self.move_type not in ('out_refund', 'in_refund'):
                    raise UserError(_('Debe registrar primero los métodos de pagos para esta factura a contado'))
            else:
                for det in payments_to_process:
                    # Determinamos tipos según sea Factura o Nota de Crédito
                    if self.move_type in ('out_invoice', 'out_receipt', 'out_refund'):
                        partner_type = 'customer'
                        # Si es Nota de Crédito cliente, el pago es una SALIDA (devolución)
                        payment_type = 'outbound' if self.move_type == 'out_refund' else 'inbound'
                    
                    elif self.move_type in ('in_invoice', 'in_receipt', 'in_refund'):
                        partner_type = 'supplier'
                        # Si es Nota de Crédito proveedor, el pago es una ENTRADA (reembolso)
                        payment_type = 'inbound' if self.move_type == 'in_refund' else 'outbound'
                    
                    vals = {
                        'partner_id': det.move_id.partner_id.id,
                        'currency_id': det.moneda.id,
                        'amount': det.monta_a_pagar,
                        'journal_id': det.account_journal_id.id,
                        'payment_method_line_id': det.account_payment_method_id.id,
                        'payment_type': payment_type,
                        'partner_type': partner_type,
                        'date': det.fecha,
                    }
                    id_payment = self.env['account.payment'].create(vals)
                    det.payment_id = id_payment
                    det.payment_id.action_post()
                    self.concilia_pago(id_payment)

    def concilia_pago(self, payment_id):
        self.ensure_one()
        # 1. Obtenemos las líneas del asiento contable del pago
        # Buscamos la línea que impacta en la cuenta por cobrar/pagar
        account_type = 'asset_receivable' if self.is_sale_document() else 'liability_payable'
        
        # Filtrar las líneas del pago que pertenecen a cuentas de cliente/proveedor
        pay_lines = payment_id.move_id.line_ids.filtered(
            lambda line: line.account_id.account_type == account_type and not line.reconciled
        )
        
        for line in pay_lines:
            # Este es el método estándar de Odoo para conciliar una línea 
            # de pago pendiente con la factura actual.
            # Evita errores de cálculo manual de residuales.
            self.js_assign_outstanding_line(line.id)


    
    def botton_borrador(self):
        self.button_draft()



    def button_draft(self):
        for selff in self:
            super().button_draft()

            if (selff.env.user.x_llevar_borra_fact=='no' or not selff.env.user.x_llevar_borra_fact) and selff.move_type in ('out_invoice','out_refund','out_receipt'):
                raise UserError(_('Su Usuario no puede llevar esta factura a borrador'))
            if selff.env.user.x_llevar_borra_fact=='si' or selff.move_type not in ('out_invoice','out_refund','out_receipt'):
                if selff.igtf_ids:
                    for det in selff.igtf_ids.search([('move_id','=',selff.id)]):
                        if det.payment_id.state!='draft':
                            det.payment_id.action_draft()
                        det.payment_id.with_context(force_delete=True).unlink()
                busca=selff.invoice_line_ids.search([('linea_exenta','=',True),('move_id','=',selff.id)])
                #raise UserError(_('HHHH %s')%busca)
                if busca:
                    busca.unlink()



    def invoice_number_seq(self):
        if not self.is_manual:
            if self.move_type in ('out_invoice','out_refund','out_receipt','in_invoice','in_refund','in_receipt'):
                if not self.invoice_number_next or self.invoice_number_next==0:
                    #self.invoice_number_next=self.journal_id.code + "/" +self.get_invoice_nro_fact()
                    self.invoice_number_next=self.get_invoice_nro_fact()

    def get_invoice_nro_fact(self):
        name=''
        if not self.journal_id.doc_sequence_id:
            raise UserError(_('Este diario no tiene configurado el Nro de Documento. Vaya al diario, pestaña *Configuracion sec. Facturación* y en el campo *Proximo Nro Documento* agregue uno'))
        else:
            if not self.journal_id.doc_sequence_id.code:
                raise UserError(_('La secuencia del Nro documento llamado * %s * de este diario, no tiene configurada el Código se secuencias')%self.journal_id.doc_sequence_id.name)
            else:
                SEQUENCE_CODE=self.journal_id.doc_sequence_id.code
                company_id = self.company_id.id
                IrSequence = self.env['ir.sequence'].with_context(force_company=company_id)
                name = IrSequence.next_by_code(SEQUENCE_CODE)
        return name

    def invoice_control(self):
        if not self.is_manual:
            if self.move_type in ('out_invoice','out_refund','out_receipt','in_invoice','in_refund','in_receipt'):
                if not self.invoice_number_control or self.invoice_number_control==0:
                    self.invoice_number_control=self.get_invoice_number_control()



    def get_invoice_number_control(self):
        name = ''
        journal = self.journal_id
        
        # 1. Validaciones iniciales de configuración
        if not journal.ctrl_sequence_id:
            raise UserError(_('Este diario no tiene configurado el Nro de control. Vaya al diario, pestaña *Configuracion sec. Facturación* y en el campo *Proximo Nro control* agregue uno.'))
        
        if not journal.ctrl_sequence_id.code:
            raise UserError(_('La secuencia del Nro control llamado * %s * de este diario, no tiene configurada el Código de secuencias.') % journal.ctrl_sequence_id.name)

        SEQUENCE_CODE = journal.ctrl_sequence_id.code
        company_id = self.company_id.id
        IrSequence = self.env['ir.sequence'].with_context(force_company=company_id)

        # 2. Generar número y validar que no exista
        while True:
            name = IrSequence.next_by_code(SEQUENCE_CODE)
            
            # Buscamos si ya existe una factura de cliente con ese número de control
            # Filtramos por tipos de factura de salida (out_invoice, out_refund, out_receipt)
            duplicate_control = self.env['account.move'].search([
                ('invoice_number_control', '=', name),
                ('move_type', 'in', ('out_invoice', 'out_refund', 'out_receipt')),
                ('company_id', '=', company_id)
            ], limit=1)

            if not duplicate_control:
                # Si no hay duplicados, salimos del bucle y devolvemos el nombre
                break
            
            # Si existe un duplicado, el bucle volverá a ejecutar next_by_code 
            # para consumir el siguiente número de la secuencia.

        return name

    
    def get_invoice_number_control_org(self):
        name=''            
        if not self.journal_id.ctrl_sequence_id:
            raise UserError(_('Este diario no tiene configurado el Nro de control. vaya al diario, pestaña *Configuracion sec. Facturación* y en el campo *Proximo Nro control* agregue uno'))
        else:
            if not self.journal_id.ctrl_sequence_id.code:
                raise UserError(_('La secuencia del Nro control llamado * %s * de este diario, no tiene configurada el Código se secuencias')%self.journal_id.ctrl_sequence_id.name)
            else:
                SEQUENCE_CODE=self.journal_id.ctrl_sequence_id.code
                company_id = self.company_id.id
                IrSequence = self.env['ir.sequence'].with_context(force_company=company_id)
                name = IrSequence.next_by_code(SEQUENCE_CODE)

        return name

    def get_nro_nota_entrega(self):
        name=''
        if self.journal_id.nota_entrega!=True:
            raise UserError(_('Este diario no esta configurado para nota de entrega. Vaya al diario, pestaña *Configuracion sec. Facturación* y habilite el campo nota de entrega'))
        if not self.journal_id.doc_sequence_id:
            raise UserError(_('Este diario no tiene configurado el Nro de nota de entrega. Vaya al diario, pestaña *Configuracion sec. Facturación* y en el campo *Proximo Nro Documento* agregue uno'))
        else:
            if not self.journal_id.doc_sequence_id.code:
                raise UserError(_('La secuencia del Nro documento llamado * %s * de este diario, no tiene configurada el Código se secuencias')%self.journal_id.doc_sequence_id.name)
            else:
                SEQUENCE_CODE=self.journal_id.doc_sequence_id.code
                company_id = self.company_id.id
                IrSequence = self.env['ir.sequence'].with_context(force_company=company_id)
                name = IrSequence.next_by_code(SEQUENCE_CODE)
        return name

    @api.onchange('invoice_line_ids','tasa','currency_id','price_ref_div_product')
    def actualiza_precio(self):
        if self.price_ref_div_product==True:
            if self.company_id.currency_id == self.currency_id:
                if self.invoice_line_ids:
                    linea_fact=self.invoice_line_ids
                    #raise UserError(_("aqui hay=%s")%linea_fact)
                    for det in linea_fact:
                        if det.product_id:
                            det.price_unit=self.tasa*det.price_unit_ref
                            self._onchange_partner_id()
            else:
                if self.invoice_line_ids:
                    linea_fact=self.invoice_line_ids
                    for det in linea_fact:
                        if det.product_id:
                            det.price_unit=det.product_id.lst_price2
                            self._onchange_partner_id()

    @api.onchange('tasa')
    def act_tasa(self):
        busca=self.env['res.currency.rate'].search([('currency_id','=',self.company_id.currency_sec_id.id),('name','<=',self.invoice_date)],order='name desc',limit=1)
        if busca:
            if busca.inverse_company_rate!=self.tasa:
                busca.write({'inverse_company_rate':self.tasa,})
            """self._onchange_quick_edit_line_ids()
            self._compute_tax_totals()
            self._compute_quick_encoding_vals()
            self._onchange_quick_edit_line_ids()
            container = {'records': self}
            self._check_balanced(container)
            self._onchange_partner_id()"""



    @contextmanager
    def _check_balanced(self, container):
        ''' Assert the move is fully balanced debit = credit.
        An error is raised if it's not the case.
        '''
        with self._disable_recursion(container, 'check_move_validity', default=True, target=False) as disabled:
            yield
            if disabled:
                return

        unbalanced_moves = self._get_unbalanced_moves(container)
        if unbalanced_moves:
            error_msg = _("An error has occurred.")
            for move_id, sum_debit, sum_credit in unbalanced_moves:
                move = self.browse(move_id)
                error_msg += _(
                    "\n\n"
                    "The move (%s) is not balanced.\n"
                    "The total of debits equals %s and the total of credits equals %s.\n"
                    "You might want to specify a default account on journal \"%s\" to automatically balance each move.",
                    move.display_name,
                    format_amount(self.env, sum_debit, move.company_id.currency_id),
                    format_amount(self.env, sum_credit, move.company_id.currency_id),
                    move.journal_id.name)
            #raise UserError(error_msg)

    


class  AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    #balance_aux=fields.Float(compute='_compute_balance_conversion')
    credit_div=fields.Float(compute='_compute_contravalor_credit')
    debit_div=fields.Float(compute='_compute_contravalor_debit')
    price_unit_ref = fields.Float(compute='_compute_price_unit_ref',store=True, readonly=0,digits=(12, 4))
    linea_exenta = fields.Boolean(default=False)


    @api.constrains('quantity', 'price_unit')
    def _check_credit_note_limits_seniat(self):
        """
        Valida que la cantidad y el precio unitario de la línea de la Nota de Crédito
        no superen los valores de la factura referenciada en el campo 'fact_afect' (número de factura).
        """
        
        for line in self.search([],order='id ASC'):
            move = line.move_id
            
            # 1. Aplicar solo a Notas de Crédito de Clientes (out_refund) 
            # y si el campo 'fact_afect' tiene el número de la factura.
            if move.move_type == 'out_refund' and move.fact_afect:
                
                # --- BÚSQUEDA DE LA FACTURA ORIGINAL POR NÚMERO ---
                # Buscar la Factura Original (out_invoice) cuyo campo 'name' coincida con 'fact_afect'.
                original_invoice = self.env['account.move'].search([
                    ('move_type', '=', 'out_invoice'), # Aseguramos que es una factura de cliente
                    ('state', 'in', ['posted', 'paid']), # Debe estar validada
                    ('invoice_number_next', '=', move.fact_afect), # El número de factura debe coincidir con 'fact_afect'
                ], limit=1)

                # ------------------------------------------------
                
                if not original_invoice:
                    # Si no encontramos la factura original, no podemos validar.
                    # Podrías lanzar un error aquí si es obligatorio, pero por ahora solo se ignora la validación.
                    continue

                else:
                    #if line.display_type:
                        #continue # Omitir líneas de sección o nota

                    # 2. Mapear las líneas de la factura original para comparación
                    # Buscamos una coincidencia de línea basada en el producto y/o descripción.
                    original_line = original_invoice.invoice_line_ids.filtered(lambda l: \
                        l.product_id.id == line.product_id.id and \
                        l.name == line.name
                    )
                    #raise UserError(_("xxx %s")%original_line)
                    if not original_line:
                        #raise UserError(_("Darrell"))
                        continue 
                    
                    # Usamos la primera coincidencia
                    original_line = original_line[0]
                    
                    # 3. Validar Cantidad
                    original_qty = original_line.quantity
                    credit_note_qty = line.quantity
                    #raise UserError(_("original_qty %s, credit_note_qty %s")%(original_line.price_unit_ref,line.price_unit_ref))
                    
                    if credit_note_qty > original_qty:
                        raise UserError(_(
                            "VALIDACIÓN SENIAT: La Cantidad (%s) de la línea '%s' no puede ser superior "
                            "a la cantidad de la factura afectada (%s) (Factura: %s)."
                        ) % (credit_note_qty, line.name, original_qty, original_invoice.name))

                        #move._log_and_raise_fiscal_error("VALIDACIÓN SENIAT: La Cantidad (%s) de la línea '%s' no puede ser superior "
                            #"a la cantidad de la factura afectada (%s) (Factura: %s)." % (credit_note_qty, line.name, original_qty, original_invoice.name))
                    
                    # 4. Validar Precio Unitario
                    aux=line.product_id.standard_price
                    if aux!=line.price_unit:
                        original_price = original_line.price_unit
                        credit_note_price = line.price_unit

                        if credit_note_price > original_price:
                            raise UserError(_(
                                "VALIDACIÓN SENIAT: El Precio Unitario (%.2f) de la línea '%s' no puede ser superior "
                                "al precio unitario de la factura afectada (%.2f) (Factura: %s)."
                            ) % (credit_note_price, line.name, original_price, original_invoice.name))

                            #move._log_and_raise_fiscal_error("VALIDACIÓN SENIAT: El Precio Unitario (%.2f) de la línea '%s' no puede ser superior "
                                #"al precio unitario de la factura afectada (%.2f) (Factura: %s)." % (credit_note_price, line.name, original_price, original_invoice.name))

    # ESTA FUNCION VALIDA QUE NO SE AGREGUEN PRODUCTOS NUEVOS EN LA NC DE CLEINETES SI NO ESTAN EN LA FACTURA AFECTADA
    @api.constrains('product_id')
    def _check_new_product_not_nc(self):
        ban=0
        for line in self:
            move_id=line.move_id

            if move_id.move_type == 'out_refund' and move_id.fact_afect:
                original_invoice = self.env['account.move'].search([
                    ('move_type', '=', 'out_invoice'), 
                    ('state', 'in', ['posted', 'paid']), 
                    ('invoice_number_next', '=', move_id.fact_afect), 
                ], limit=1)
                if original_invoice:
                    lineas_fact_org=original_invoice.invoice_line_ids.search([('move_id','=',original_invoice.id)])
                    #raise UserError(_("Lineas Original %s")%lineas_fact_org)
                    if lineas_fact_org:
                        for det in lineas_fact_org:
                            if det.product_id==line.product_id:
                                ban=1

                if ban==0:
                    raise UserError(_("🛑 VALIDACIÓN SENIAT: El producto/descripción *%s* no pertenece a la factura afectada *%s*"
                    " No se Permiten agregar productos que no hayan sido previamente facturados. ")% (line.product_id.name, original_invoice.name))

                    #move_id._log_and_raise_fiscal_error("🛑 VALIDACIÓN SENIAT: El producto/descripción *%s* no pertenece a la factura afectada *%s*"
                    #" No se Permiten agregar productos que no hayan sido previamente facturados." % (line.product_id.name, original_invoice.name))




    @api.onchange('tax_ids')
    def impuestos_varios(self):
        cont=0
        tax_aux_id=0
        if self.tax_ids:
            for lista in self.tax_ids:
                cont=cont+1
            if cont>1:
                self.tax_ids = [(5, 0, 0)] # Borra todos los impuestos si no hay uno único


    def _compute_contravalor_credit(self):
        valor=0
        for selff in self:
            valor=selff.credit/selff.move_id.tasa if selff.move_id.tasa!=0 else selff.credit
            selff.credit_div=valor

    def _compute_contravalor_debit(self):
        valor=0
        for selff in self:
            valor=selff.debit/selff.move_id.tasa if selff.move_id.tasa!=0 else selff.debit
            selff.debit_div=valor

    @api.depends('product_id')
    def _compute_price_unit_ref(self):
        for selff in self:
            selff.price_unit_ref=selff.product_id.lst_price2

class AccountPagosFacturas(models.Model):
    _name = 'account.payment.fact'

    move_id = fields.Many2one('account.move')#
    tasa = fields.Float(digits=(12, 4))#
    porcentage = fields.Float(compute='_compute_porcentage')#
    monta_a_pagar = fields.Float()#
    monta_a_pagar_bs = fields.Float(compute='_compute_eq_bs')#
    monto_ret_bs = fields.Float(compute='_compute_ret')#
    moneda = fields.Many2one('res.currency')#
    company_id = fields.Many2one('res.company',default=lambda self: self.env.company)
    account_journal_id = fields.Many2one('account.journal',string="Diario")#
    account_payment_method_id = fields.Many2one('account.payment.method.line')#
    payment_id=fields.Many2one('account.payment')
    asiento_igtf=fields.Many2one('account.move',help='Aqui se refleja el asiento del igtf solo si el pago se realiza a credito')
    fecha=fields.Date()

    @api.onchange('monta_a_pagar')
    @api.depends('monta_a_pagar')
    def _compute_eq_bs(self):
        for selff in self:
            if selff.moneda.id!=selff.company_id.currency_id.id:
                valor=selff.tasa*selff.monta_a_pagar
            else:
                valor=selff.monta_a_pagar
            selff.monta_a_pagar_bs=valor

    def _compute_ret(self):
        for selff in self:
            if selff.move_id.journal_id.nota_entrega!=True and selff.move_id.journal_id.tipo_doc!='ne':
                valor=selff.monta_a_pagar_bs*selff.porcentage/100
                selff.monto_ret_bs=valor
            else:
                selff.monto_ret_bs=0


    def _compute_porcentage(self):
        for selff in self:
            if selff.moneda.id!=selff.company_id.currency_id.id:
                valor=selff.company_id.percentage_cli_igtf
            else:
                valor=0
            if selff.move_id.journal_id.nota_entrega==True or selff.move_id.journal_id.tipo_doc=='ne':
                valor=0
            selff.porcentage=valor