from datetime import datetime, timedelta
from odoo.tools.misc import DEFAULT_SERVER_DATE_FORMAT

from odoo import models, fields, api, _, tools
from odoo.exceptions import UserError
import logging

import io
from io import BytesIO

import xlsxwriter
import shutil
import base64
import csv
import xlwt
import xml.etree.ElementTree as ET





class ResumenIslrModelo(models.Model):
    _name = "resumen.igtf.wizard.pdf"

    move_id = fields.Many2one('account.move')
    tipo_igtf_prov=fields.Char()
    metodo_pago = fields.Many2one('account.payment.method.line')
    monto_base_usd = fields.Float()
    tasa = fields.Float()
    monto_base = fields.Float()
    porcentaje = fields.Float()
    monto_ret = fields.Float()

    #diario=fields.Many2one('account.jornal')
    #asiento_igtf = fields.Many2one('account.move')
    #payment_id = fields.Many2one('account.payment')

    def formato_fecha(self,date):
        fecha = str(date)
        fecha_aux=fecha
        ano=fecha_aux[0:4]
        mes=fecha[5:7]
        dia=fecha[8:10]  
        resultado=dia+"/"+mes+"/"+ano
        return resultado

    def float_format2(self,valor):
        #valor=self.base_tax
        if valor:
            result = '{:,.2f}'.format(valor)
            result = result.replace(',','*')
            result = result.replace('.',',')
            result = result.replace('*','.')
        else:
            result="0,00"
        return result

    def tipo_trans(self,valor):
        resultado=""
        if valor=="div":
            resultado="Pag. En Divisas"
        if valor=="bank":
            resultado="Pag. por Bancos"
        return resultado


class WizardReport_2(models.TransientModel): # aqui declaro las variables del wizar que se usaran para el filtro del pdf
    _name = 'wizard.resumen.igtf'
    _description = "Resumen Retenciones islr"

    tipo_empresa = fields.Selection([('supplier','Proveedor'),('customer','Cliente')])
    tipo_pago = fields.Selection([('payment_fact','Incluyendo Facturas'),('payment','Sin incluir Facturas')], default='payment_fact',readonly=True)
    date_from  = fields.Date('Date From', default=lambda *a:(datetime.now() - timedelta(days=(1))).strftime('%Y-%m-%d'))
    date_to = fields.Date(string='Date To', default=lambda *a:datetime.now().strftime('%Y-%m-%d'))
    date_actual = fields.Date(default=lambda *a:datetime.now().strftime('%Y-%m-%d'))

    company_id = fields.Many2one('res.company','Company',default=lambda self: self.env.company.id)
    line_igtf  = fields.Many2many(comodel_name='resumen.igtf.wizard.pdf', string='Lineas')


    def tipo(self,valor):
        if valor=="supplier":
            resultado="PROVEEDORES"
        if valor=="customer":
            resultado="CLIENTES"
        return resultado

    def formato_fecha(self,date):
        fecha = str(date)
        fecha_aux=fecha
        ano=fecha_aux[0:4]
        mes=fecha[5:7]
        dia=fecha[8:10]  
        resultado=dia+"/"+mes+"/"+ano
        return resultado

    def float_format2(self,valor):
        #valor=self.base_tax
        if valor:
            result = '{:,.2f}'.format(valor)
            result = result.replace(',','*')
            result = result.replace('.',',')
            result = result.replace('*','.')
        else:
            result="0,00"
        return result

    def get_paymet(self):
        t=self.env['resumen.igtf.wizard.pdf']
        d=t.search([])
        d.unlink()
        cursor = self.env['account.payment'].search([('date','>=',self.date_from),('date','<=',self.date_to),('partner_type','=',self.tipo_empresa)],order='date asc')
        if cursor:
            for rec in cursor:
                if rec.asiento_cobro_igtf!=False or rec.asiento_prov_igtf_bank!=False:
                    if rec.asiento_cobro_igtf:
                        tasa=(rec.move_id.amount_total_signed/rec.move_id.amount_total)
                        values={
                        'asiento_igtf':rec.asiento_cobro_igtf.id,
                        'metodo_pago':rec.payment_method_id.id,
                        'monto_base_usd':rec.amount,
                        'tasa':tasa,
                        'monto_base':rec.amount*tasa,
                        'porcentaje':rec.payment_method_id.wh_porcentage,
                        'monto_ret':rec.asiento_cobro_igtf.amount_total_signed,
                        'tipo_igtf_prov':"div",
                        'diario':rec.journal_id.id,
                        'payment_id':rec.id,
                        }
                        pdf_id = t.create(values)
                    if rec.asiento_prov_igtf_bank:
                        vals={
                        'asiento_igtf':rec.asiento_prov_igtf_bank.id,
                        'metodo_pago':rec.payment_method_id.id,
                        'monto_base_usd':rec.amount if rec.currency_id!=self.env.company.currency_id.id else 0.0,
                        'tasa':tasa,
                        'monto_base':rec.amount*tasa,
                        'porcentaje':rec.journal_id.wh_porcentage,
                        'monto_ret':rec.asiento_prov_igtf_bank.amount_total_signed,
                        'tipo_igtf_prov':"bank",
                        'diario':rec.journal_id.id,
                        'payment_id':rec.id,
                        }
                        pdf_id = t.create(vals)
                    self.line_igtf = self.env['resumen.igtf.wizard.pdf'].search([])
                    #raise UserError(_('Cursor = %s')%rec.id)
        else:
            raise UserError(_('No hay nada que reportar para estas fechas'))


    def get_invoice(self):
        if self.tipo_empresa=="customer":
            move_type=('out_invoice','out_refund','out_receipt')
        if self.tipo_empresa=="supplier":
            move_type=('in_invoice','in_refund','in_receipt')
        t=self.env['resumen.igtf.wizard.pdf']
        d=t.search([])
        d.unlink()
        cursor_resumen = self.env['account.payment.fact'].search([
            ('move_id.invoice_date','>=',self.date_from),
            ('move_id.invoice_date','<=',self.date_to),
            ('move_id.state','=','posted'),
            ('move_id.company_id','=',self.company_id.id),
            ('move_id.move_type','in',move_type),
            ('moneda','!=',self.company_id.currency_id.id),
            ])
        if not cursor_resumen:
            raise UserError(_('No hay nada que reportar para estas fechas'))
        else:  
            for det in cursor_resumen:
                values={
                'move_id':det.move_id.id,
                #'asiento_igtf':det.asiento_igtf.id,
                'metodo_pago':det.account_payment_method_id.id,
                'monto_base_usd':det.monta_a_pagar,
                'tasa':det.tasa,
                'monto_base':det.monta_a_pagar_bs,
                'porcentaje':det.porcentage,
                'monto_ret':det.monto_ret_bs,
                ###'id_code':id_code.id,
                }
                pdf_id = t.create(values)
            self.line_igtf = self.env['resumen.igtf.wizard.pdf'].search([])

    


    def print_resumen_igtf(self):
        w=self.env['wizard.resumen.igtf'].search([('id','!=',self.id)])
        w.unlink()
        if self.tipo_pago=="payment_fact":
            self.get_invoice()
            return self.env.ref('base_contable.action_libro_resumen_igtf').report_action(self)