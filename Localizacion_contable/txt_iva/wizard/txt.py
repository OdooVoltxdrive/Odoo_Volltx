# # -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from odoo import models, fields, api, _, tools
from odoo.exceptions import UserError, ValidationError
#import openerp.addons.decimal_precision as dp
import logging

import io
from io import BytesIO
from io import StringIO

import xlsxwriter
import shutil
import base64
import csv

import urllib.request

import requests

_logger = logging.getLogger(__name__)

"""def rif_format(valor):
    if valor:
        return valor.replace('-','')
    return '0'"""

def tipo_format(valor):
    if valor and valor=='in_refund':
        return '03'
    return '01'

def float_format(valor):
    if valor:
        result = '{:,.2f}'.format(valor)
        #_logger.info('Result 1: %s' % result)
        result = result.replace(',','')
        #_logger.info('Result 2: %s' % result)
        return result
    return valor

def float_format2(valor):
    #valor=self.base_tax
    if valor:
        result = '{:,.2f}'.format(valor)
        #result = result.replace(',','*')
        #esult = result.replace('.',',')
        #result = result.replace('*','.')
        result = result.replace(',','')
    else:
        result="0.00"
    return result

def completar_cero(campo,digitos):
    valor=len(campo)
    campo=str(campo)
    nro_ceros=digitos-valor+1
    for i in range(1,nro_ceros,1):
        campo=" "+campo
    return campo

def formato_periodo(valor):
        fecha = str(valor)
        fecha_aux=fecha
        ano=fecha_aux[0:4]
        mes=fecha[5:7]
        dia=fecha[8:10]  
        resultado=ano+mes
        return resultado

def rif_format(partner_id):
    nro_doc = '*****' 
    if partner_id.vat:
        nro_doc=partner_id.vat    
    resultado=str(nro_doc.replace('-', ''))
    return resultado
    #raise UserError(_('cedula: %s')%resultado)

class BsoftContratoReport2(models.TransientModel):
    _name = 'snc.wizard.retencioniva'
    _description = 'Generar archivo TXT de retenciones de IVA'

    delimiter = '\t'
    quotechar = "'"
    date_from = fields.Date(string='Fecha de Llegada', default=lambda *a:datetime.now().strftime('%Y-%m-%d'))
    date_to = fields.Date(string='Fecha de Salida', default=lambda *a:(datetime.now() + timedelta(days=(1))).strftime('%Y-%m-%d'))
    file_data = fields.Binary('Archivo TXT', filters=None, help="")
    file_name = fields.Char('txt_generacion.txt', size=256, required=False, help="",)

    def show_view(self, name, model, id_xml, res_id=None, view_mode='tree,form', nodestroy=True, target='new'):
        context = self._context
        mod_obj = self.env['ir.model.data']
        view_obj = self.env['ir.ui.view']
        module = ""
        view_id = self.env.ref(id_xml).id
        if view_id:
            view = view_obj.browse(view_id)
            view_mode = view.type
        ctx = context.copy()
        ctx.update({'active_model': model})
        res = {'name': name,
                'view_type': 'form',
                'view_mode': view_mode,
                'view_id': view_id,
                'res_model': model,
                'res_id': res_id,
                'nodestroy': nodestroy,
                'target': target,
                'type': 'ir.actions.act_window',
                'context': ctx,
                }
        return res

    

    def conv_div(self,move_id,valor):
        #raise UserError(_('moneda compañia: %s')%self.company_id.currency_id.id)
        if move_id.company_id.currency_id.id!=move_id.currency_id.id:
            tasa= self.env['account.move'].search([('id','=',move_id.id)],order="id asc",limit=1)
            for det in tasa:
                valor_aux=det.tasa
            rate=round(valor_aux,3)  # LANTA
            #rate=round(valor_aux,2)  # ODOO SH
            resultado=valor*rate
        else:
            resultado=valor
        return resultado



    def action_generate_txt(self):

        ret_cursor = self.env['account.move'].search([('date','>=',self.date_from),('date','<=',self.date_to),('move_type','in',('in_invoice','in_refund','in_receipt')),('state','=','posted'),],order="date asc")
        #_logger.info("\n\n\n {} \n\n\n".format(self.rec_cursor))
        #raise UserError(_(' id retencion:%s')%rec_cursor.vat_ret_id.id) 

        self.file_name = 'txt_generacion.txt'
        retiva = self.env['vat.retention']
        retiva = str(retiva.name)

        ruta=self.env.company.x_ruta_txt_iva
        #ruta="C:/REPOSITORIO/gilda_temp/localizacion_18/txt_iva/wizard/txt_generacion.txt" #ruta local
        #ruta="/home/odoo/src/txt_generacion.txt" # ruta odoo sh
        #raise UserError(_('mama = %s')%rec.type)

        with open(ruta, "w") as file:

            for ret in ret_cursor:
                if ret.vat_ret_id:
                    if ret.vat_ret_id.state=="posted":
                        if ret.move_type=="in_invoice":
                            trans='01'
                        if ret.move_type=="in_refund":
                            trans='03'
                        if ret.move_type=='in_receipt':
                            trans='02'

                        acum_exemto=base_general=base_reducida=base_adicional=0
                        
                        busca_exento = ret.alicuota_line_ids.search([('invoice_id','=',ret.id)])
                        for det in busca_exento:
                            acum_exemto=acum_exemto+det.base_exenta
                            base_general=base_general+det.base_general
                            base_reducida=base_reducida+det.base_reducida
                            base_adicional=base_adicional+det.base_adicional

                        rec_cursor = self.env['vat.retention.invoice.line'].search([('retention_id','=',ret.vat_ret_id.id)])
                        for rec in rec_cursor:

                            if rec.tax_id.aliquot!="exempt":
                                rif_compania=rif_format(rec.invoice_id.company_id.partner_id)
                                file.write(rif_compania + "\t")#1

                                periodo=formato_periodo(self.date_to)
                                file.write(periodo + "\t")#2

                                fecha = rec.invoice_id.date
                                fecha = str(fecha)
                                file.write(fecha + "\t")#3

                                file.write("C" + "\t")#4

                                file.write(trans + "\t") #5

                                rif_proveedor= rif_format(rec.invoice_id.partner_id)
                                file.write(rif_proveedor + "\t") #6

                                invoicer_number=str(rec.invoice_id.invoice_number_next)
                                #invoicer_number=completar_cero(invoicer_number,10)
                                file.write(invoicer_number + "\t") #7

                                invoice_sequence = str(rec.invoice_id.invoice_number_control)
                                #invoice_sequence = completar_cero(invoice_sequence,10)
                                file.write(invoice_sequence + "\t") #8

                                total = str(float_format2(abs(rec.invoice_id.amount_total_signed)))
                                #total = completar_cero(total,12)
                                file.write(total + "\t") #9

                                #############################
                                if base_general!=0 and base_adicional==0 and base_reducida==0:
                                    importe_base = str(float_format2(self.conv_div(ret,abs(base_general))))
                                if base_general==0 and base_adicional==0 and base_reducida!=0:
                                    importe_base = str(float_format2(self.conv_div(ret,abs(base_reducida))))
                                if base_general==0 and base_adicional!=0 and base_reducida==0:
                                    importe_base = str(float_format2(self.conv_div(ret,abs(base_adicional))))
                                file.write(importe_base + "\t") #10

                                monto_ret=str(float_format2(ret.vat_ret_id.vat_retentioned)) # PREGUNTAR
                                file.write(monto_ret + "\t") #11

                                #############################
                                if rec.invoice_id.fact_afect==False:
                                    fact_afec='0'
                                else:
                                    fact_afec = str(rec.invoice_id.fact_afect)
                                #fact_afec = completar_cero(fact_afec,5)
                                file.write(fact_afec + "\t") #12

                                nro_comprobante = str(rec.retention_id.name)
                                file.write(nro_comprobante + "\t") #13

                                total_exento=abs(acum_exemto)
                                total_exento=str(float_format2(self.conv_div(ret,total_exento)))
                                file.write(total_exento + "\t")#14

                                porcentage_iva=rec.tax_id.amount
                                porcentage_iva = str(round(porcentage_iva))
                                #porcentage_iva = completar_cero(porcentage_iva,5)
                                file.write(porcentage_iva + "\t") #15 PREGUNTAR"""

                                

                                file.write('0' + "\n") #16



        #self.write({'file_data': base64.encodestring(open(ruta, "rb").read()),
                    #'file_name': "Retenciones de IVA desde %s hasta %s.txt"%(self.date_from,self.date_to),
                    #})
        self.write({'file_data': base64.encodebytes(open(ruta, "rb").read()),
                    'file_name': "Retenciones de IVA desde %s hasta %s.txt"%(self.date_from,self.date_to),
                    })

        return self.show_view('Archivo Generado', self._name, 'txt_iva.snc_wizard_retencioniva_form_view', self.id)
