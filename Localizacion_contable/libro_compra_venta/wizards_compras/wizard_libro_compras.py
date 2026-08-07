from datetime import datetime, timedelta
from odoo.tools.misc import DEFAULT_SERVER_DATE_FORMAT

from odoo import models, fields, api, _, tools
from odoo.exceptions import UserError
#import openerp.addons.decimal_precision as dp
import logging

import io
from io import BytesIO

import xlsxwriter
import shutil
import base64
import csv
import xlwt

_logger = logging.getLogger(__name__)

class LibroVentasModelo(models.Model):
    _name = "account.wizard.pdf.compras" 

    name = fields.Date(string='Fecha')
    document = fields.Char(string='Rif')
    partner  = fields.Many2one(comodel_name='res.partner', string='Partner')
    invoice_number =   fields.Char(string='invoice_number')
    tipo_doc = fields.Char(string='tipo_doc')
    invoice_ctrl_number = fields.Char(string='invoice_ctrl_number')
    sale_total = fields.Float(string='invoice_ctrl_number')
    base_imponible = fields.Float(string='invoice_ctrl_number')
    iva = fields.Float(string='iva')
    iva_retenido = fields.Float(string='iva retenido')
    retenido = fields.Char(string='retenido')
    retenido_date = fields.Date(string='date')
    alicuota = fields.Char(string='alicuota')
    alicuota_type = fields.Char(string='alicuota type')
    state_retantion = fields.Char(string='state')
    state = fields.Char(string='state')
    reversed_entry_id = fields.Many2one('account.move', string='Facturas', store=True)
    currency_id = fields.Many2one('res.currency', 'Currency')
    ref = fields.Char(string='ref')

    total_exento = fields.Float(string='Total Excento')
    alicuota_reducida = fields.Float(string='Alicuota Reducida')
    alicuota_general = fields.Float(string='Alicuota General')
    alicuota_adicional = fields.Float(string='Alicuota General + Reducida')

    base_general = fields.Float(string='Total Base General')
    base_reducida = fields.Float(string='Total Base Reducida')
    base_adicional = fields.Float(string='Total Base General + Reducida')

    retenido_general = fields.Float(string='retenido General')
    retenido_reducida = fields.Float(string='retenido Reducida')
    retenido_adicional = fields.Float(string='retenido General + Reducida')

    vat_ret_id = fields.Many2one('vat.retention', string='Nro de Comprobante IVA')
    invoice_id = fields.Many2one('account.move')
    tax_id = fields.Many2one('account.tax', string='Tipo de Impuesto')

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


    def conv_div(self,valor):
        self.invoice_id.currency_id.id
        fecha_contable_doc=self.invoice_id.date
        monto_factura=self.invoice_id.amount_total
        valor_aux=0
        prueba=valor
        #raise UserError(_('moneda compañia: %s')%self.company_id.currency_id.id)
        if self.invoice_id.company_id.currency_id.id!=self.currency_id.id:
            tasa= self.env['account.move'].search([('id','=',self.invoice_id.id)],order="id asc")
            for det_tasa in tasa:
                monto_nativo=det_tasa.amount_untaxed_signed
                monto_extran=det_tasa.amount_untaxed
                valor_aux=abs(monto_nativo/monto_extran)
            rate=round(valor_aux,3)  # LANTA
            #rate=round(valor_aux,2)  # ODOO SH
            resultado=valor*rate
        else:
            resultado=valor
        return resultado

    def float_format_div(self,valor):
        #valor=self.base_tax
        if valor:
            result = '{:,.2f}'.format(valor)
            result = result.replace(',','*')
            result = result.replace('.',',')
            result = result.replace('*','.')
        else:
            result="0,00"
        return result

    def doc_cedula(self,aux):
        #nro_doc=self.partner_id.vat
        nro_doc="00000000"
        tipo_doc="V"
        busca_partner = self.env['res.partner'].search([('id','=',aux)])
        for det in busca_partner:
            tipo_doc=det.doc_tipo
            if det.vat:
                nro_doc=str(det.vat)
            else:
                nro_doc="V00000000" 
        resultado=str(nro_doc)
        return resultado
        #raise UserError(_('cedula: %s')%resultado)

class libro_ventas(models.TransientModel):
    _name = "account.wizard.libro.compras" ## = nombre de la carpeta.nombre del archivo deparado con puntos

    facturas_ids = fields.Many2many('account.move', string='Facturas', store=True) ##Relacion con el modelo de la vista de la creacion de facturas
    retiva_ids = 0 ## Malo

    tax_ids = fields.Many2many('account.tax', string='Facturas_1', store=True)

    #line_tax_ids = fields.Many2many('account.move.line.tax', string='Facturas_2', store=True)
    line_ids = fields.Many2many('account.move.line', string='Facturas_3', store=True)
    #invoice_ids = fields.Char(string="idss", related='facturas_ids.id')

    date_from = fields.Date(string='Date From', default=lambda *a:datetime.now().strftime('%Y-%m-%d'))
    date_to = fields.Date('Date To', default=lambda *a:(datetime.now() + timedelta(days=(1))).strftime('%Y-%m-%d'))

    # fields for download xls
    state = fields.Selection([('choose', 'choose'), ('get', 'get')],default='choose') ##Genera los botones de exportar xls y pdf como tambien el de cancelar
    report = fields.Binary('Prepared file', filters='.xls', readonly=True)
    name = fields.Char('File Name', size=32)
    company_id = fields.Many2one('res.company','Company',default=lambda self: self.env.company.id)

    line  = fields.Many2many(comodel_name='account.wizard.pdf.compras', string='Lineas')
    
    def conv_div_nac(self,valor,selff):
        selff.invoice_id.currency_id.id
        fecha_contable_doc=selff.invoice_id.date
        monto_factura=selff.invoice_id.amount_total
        valor_aux=0
        prueba=22
        #raise UserError(_('moneda compañia: %s')%self.company_id.currency_id.id)
        if selff.invoice_id.currency_id.id!=self.company_id.currency_id.id:
            rate=round(selff.invoice_id.tasa,4)
            resultado=valor*rate
        else:
            resultado=valor
        return resultado

    def get_company_address(self):
        location = ''
        streets = ''
        if self.company_id:
            streets = self._get_company_street()
            location = self._get_company_state_city()
        _logger.info("\n\n\n street %s location %s\n\n\n", streets, location)
        return  (streets + " " + location)

    def _get_company_street(self):
        street2 = ''
        av = ''
        if self.company_id.street:
            av = str(self.company_id.street or '')
        if self.company_id.street2:
            street2 = str(self.company_id.street2 or '')
        result = av + " " + street2
        return result


    def _get_company_state_city(self):
        state = ''
        city = ''
        if self.company_id.state_id:
            state = "Edo." + " " + str(self.company_id.state_id.name or '')
            _logger.info("\n\n\n state %s \n\n\n", state)
        if self.company_id.city:
            city = str(self.company_id.city or '')
            _logger.info("\n\n\n city %s\n\n\n", city)
        result = city + " " + state
        _logger.info("\n\n\n result %s \n\n\n", result)
        return  result


    def doc_cedula2(self,aux):
        #nro_doc=self.partner_id.vat
        busca_partner = self.env['res.partner'].search([('id','=',aux)])
        for det in busca_partner:
            nro_doc=str(det.vat)
        resultado=str(nro_doc)
        return resultado
    

    def get_invoice(self):
        t=self.env['account.wizard.pdf.compras']
        d=t.search([])
        d.unlink()
        cursor_resumen = self.env['account.move.line.resumen'].search([
            ('fecha_fact','>=',self.date_from),
            ('fecha_fact','<=',self.date_to),
            ('state','in',('posted','cancel' )),
            ('move_type','in',('in_invoice','in_refund','in_receipt')),
            ('company_id','=',self.company_id.id),
            ('invoice_id.invoice_number_next','!=',None)
            ],order='fecha_fact asc, id asc')
        for det in cursor_resumen:
            values={
            'name':det.fecha_fact,
            'document':det.invoice_id.name,
            'partner':det.invoice_id.partner_id.id,
            'invoice_number': det.invoice_id.invoice_number_next,#darrell
            'tipo_doc': det.tipo_doc,
            'invoice_ctrl_number': det.invoice_id.invoice_number_control,
            'sale_total': self.conv_div_nac(det.total_fact,det),
            #'base_imponible': self.conv_div_nac(det.total_base,det),
            #'iva' : self.conv_div_nac(det.total_valor_iva,det),
            'iva_retenido': det.invoice_id.vat_ret_id.vat_retentioned, #self.conv_div_nac(det.invoice_id.vat_ret_id.vat_retentioned,det),
            'retenido': det.invoice_id.vat_ret_id.name,
            'retenido_date':det.vat_ret_id.voucher_delivery_date,
            'state_retantion': det.vat_ret_id.state,
            'state': det.invoice_id.state,
            'currency_id':det.invoice_id.currency_id.id,
            'ref':det.invoice_id.fact_afect,
            'total_exento':self.conv_div_nac(det.base_exenta,det),
            'alicuota_reducida':self.conv_div_nac(det.impuesto_reducida,det),
            'alicuota_general':self.conv_div_nac(det.impuesto_general,det),
            'alicuota_adicional':self.conv_div_nac(det.impuesto_adicional,det),
            'base_adicional':self.conv_div_nac(det.base_adicional,det),
            'base_reducida':self.conv_div_nac(det.base_reducida,det),
            'base_general':self.conv_div_nac(det.base_general,det),
            #'retenido_reducida':self.conv_div_nac(det.retenido_reducida,det),
            #'retenido_adicional':self.conv_div_nac(det.retenido_adicional,det),
            #'retenido_general':self.conv_div_nac(det.retenido_general,det),
            'vat_ret_id':det.invoice_id.vat_ret_id.id,
            'invoice_id':det.invoice_id.id,
            #'tax_id':det.tax_id.id,
            }
            pdf_id = t.create(values)
        #   temp = self.env['account.wizard.pdf.ventas'].search([])
        self.line = self.env['account.wizard.pdf.compras'].search([])


    def print_facturas(self):
        self.get_invoice()
        ###return self.env.ref('libro_ventas.libro_factura_clientes').report_action(self)
        #return {'type': 'ir.actions.report','report_name': 'libro_compra_venta.reporte_libro_compras','report_type':"qweb-pdf"}
        return self.env.ref('libro_compra_venta.action_libro_compra_report').report_action(self)




    def cont_row(self):
        row = 0
        for record in self.facturas_ids:
            row +=1
        return row

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

    def float_format_div2(self,valor):
        #valor=self.base_tax
        if valor:
            result = '{:,.2f}'.format(valor)
            result = result.replace(',','*')
            result = result.replace('.',',')
            result = result.replace('*','.')
        else:
            result="0,00"
        return result


# *******************  REPORTE EN EXCEL ****************************

    def generate_xls_report(self):
        #raise UserError(_('En Construcción'))
        self.get_invoice()
        #if not self.line:
            #raise UserError(_("No se encontraron registros para las fechas seleccionadas."))

        wb1 = xlwt.Workbook(encoding='utf-8')
        ws1 = wb1.add_sheet('Compras')
        fp = BytesIO()

        header_content_style = xlwt.easyxf("font: name Helvetica size 20 px, bold 1, height 170;")
        header_content_style_negri = xlwt.easyxf("font: name Helvetica size 20 px, bold 1, height 170; align: horiz right")
        header_content_style_center = xlwt.easyxf("font: name Helvetica size 20 px, color white, bold 1, height 170;pattern: fore_colour black, pattern solid ;align: horiz center; borders: left thin, right thin, top thin, bottom thin")
        header_content_style_center_v = xlwt.easyxf("font: name Helvetica size 20 px, color white, bold 1, height 170;pattern: fore_colour green, pattern solid ;align: horiz center; borders: left thin, right thin, top thin, bottom thin")
        sub_header_style = xlwt.easyxf("font: name Helvetica size 10 px, bold 1, height 170; borders: left thin, right thin, top thin, bottom thin;")
        sub_header_style_c = xlwt.easyxf("font: name Helvetica size 10 px, bold 1, height 170, color white; pattern: fore_colour black, pattern solid; borders: left thin, right thin, top thin, bottom thin; align: horiz center")
        sub_header_style_r = xlwt.easyxf("font: name Helvetica size 10 px, height 170; align: horiz right")
        sub_header_style_l = xlwt.easyxf("font: name Helvetica size 10 px, height 170; align: horiz left")
        sub_header_content_style = xlwt.easyxf("font: name Helvetica size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Helvetica, height 170;")
        row = 0
        col = 0
        ws1.row(row).height = 500

        ws1.write_merge(row, row, 2, 4,  str(self.company_id.name), header_content_style)
        rif="R.I.F: "+self.company_id.partner_id.vat
        ws1.write_merge(row, row, 5, 6,  rif, header_content_style)
        row=row+1
        ws1.write_merge(row, row, 2, 4,  "Libro de Compras", header_content_style)
        direccion="Dirección Fiscal: "+self.company_id.partner_id.street
        ws1.write_merge(row, row, 5, 10,  direccion, header_content_style)
        row=row+1
        ws1.write(row, 2, "Desde :", sub_header_style)
        fec_desde = self.line.formato_fecha2(self.date_from)
        ws1.write(row, 3, fec_desde, sub_header_content_style)
        ws1.write(row, 4, "Hasta :", sub_header_style)
        fec_hasta = self.line.formato_fecha2(self.date_to)
        ws1.write(row, 5, fec_hasta, sub_header_content_style)

        row=row+2
        ws1.write_merge(row, row, 16, 21,  "Compras Internas Nacionales", header_content_style_center_v)
        row=row+1
        ws1.write_merge(row, row, 16, 17,  "Alicuota General (16%)", header_content_style_center)
        ws1.write_merge(row, row, 18, 19,  "Alicuota Reducida (8%)", header_content_style_center)
        ws1.write_merge(row, row, 20, 21,  "Alicuota Gral+Adicional", header_content_style_center)
        ws1.write_merge(row, row, 22, 22,  "IVA Retenido", header_content_style_center)

        #CABECERA DE LA TABLA
        row=row+1
        ws1.col(col+0).width = int(len('Nro de Operación')*256)
        ws1.write(row,col+0,"Nro de Operación",sub_header_style_c)

        ws1.col(col+1).width = int(len('Fecha del Documento')*256)
        ws1.write(row,col+1,"Fecha del Documento",sub_header_style_c)

        ws1.col(col+2).width = int(len('Nro. R.I.F.')*256)
        ws1.write(row,col+2,"Nro. R.I.F.",sub_header_style_c)

        ws1.col(col+3).width = int(len('Nombre o Razón Social')*256)
        ws1.write(row,col+3,"Nombre o Razón Social",sub_header_style_c)

        ws1.col(col+4).width = int(len('Nro de Factura')*256)
        ws1.write(row,col+4,"Nro de Factura",sub_header_style_c)

        ws1.col(col+5).width = int(len('Nro de Control Factura')*256)
        ws1.write(row,col+5,"Nro de Control Factura",sub_header_style_c)

        ws1.col(col+6).width = int(len('Nro Nota de Débito')*256)
        ws1.write(row,col+6,"Nro Nota de Débito",sub_header_style_c)

        ws1.col(col+7).width = int(len('Nro Nota Crédito')*256)
        ws1.write(row,col+7,"Nro Nota Crédito",sub_header_style_c)

        ws1.col(col+8).width = int(len('Tipo de Transacción')*256)
        ws1.write(row,col+8,"Tipo de Transacción",sub_header_style_c)

        ws1.col(col+9).width = int(len('Nro Factura Afectada')*256)
        ws1.write(row,col+9,"Nro Factura Afectada",sub_header_style_c)

        ws1.col(col+10).width = int(len('Fecha Comp. Ret.')*256)
        ws1.write(row,col+10,"Fecha Comp. Ret.",sub_header_style_c)

        ws1.col(col+11).width = int(len('Nro de Comprobante de Retención')*256)
        ws1.write(row,col+11,"Nro de Comprobante de Retención",sub_header_style_c)

        ws1.col(col+12).width = int(len('Total Compras Internas incluido IVA')*256)
        ws1.write(row,col+12,"Total Compras Internas incluido IVA",sub_header_style_c)

        ws1.col(col+13).width = int(len('Compras por Cuentas de Terceros')*256)
        ws1.write(row,col+13,"Compras por Cuentas de Terceros",sub_header_style_c)

        ws1.col(col+14).width = int(len('Compras Int. Exentas o Exoneradas')*256)
        ws1.write(row,col+14,"Compras Int. Exentas o Exoneradas",sub_header_style_c)

        ws1.col(col+15).width = int(len('Compras No Sujetas')*256)
        ws1.write(row,col+15,"Compras No Sujetas",sub_header_style_c)

        ws1.col(col+16).width = int(len('Base Imponible')*256)
        ws1.write(row,col+16,"Base Imponible",sub_header_style_c)

        ws1.col(col+17).width = int(len('Impuesto IVA')*256)
        ws1.write(row,col+17,"Impuesto IVA",sub_header_style_c)

        ws1.col(col+18).width = int(len('Base Imponible')*256)
        ws1.write(row,col+18,"Base Imponible",sub_header_style_c)

        ws1.col(col+19).width = int(len('Impuesto IVA')*256)
        ws1.write(row,col+19,"Impuesto IVA",sub_header_style_c)

        ws1.col(col+20).width = int(len('Base Imponible')*256)
        ws1.write(row,col+20,"Base Imponible",sub_header_style_c)

        ws1.col(col+21).width = int(len('Impuesto IVA')*256)
        ws1.write(row,col+21,"Impuesto IVA",sub_header_style_c)

        ws1.col(col+22).width = int(len('(al vendedor)')*256)
        ws1.write(row,col+22,"(al vendedor)",sub_header_style_c)

        center = xlwt.easyxf("align: horiz center")
        right = xlwt.easyxf("align: horiz right")
        numero = 1
        contador=0
        acum_compra_iva=0
        acum_exento=0
        acum_base_general=0
        acum_ali_general=0
        acum_base_reducida=0
        acum_ali_reducida=0
        acum_base_adicional=0
        acum_ali_adicional=0
        acum_retenidos=0

        if self.line:
            for invoice in self.line.sorted(key=lambda x: (x.name,x.id),reverse=False):
            #for invoice in self.line.sorted(key=lambda x: (x.name),reverse=False):
                row=row+1
                ws1.write(row,col+0,str(numero),center)
                numero=numero+1
                ws1.write(row,col+1,str(invoice.formato_fecha2(invoice.invoice_id.invoice_date)),center)
                ws1.write(row,col+2,str(invoice.doc_cedula(invoice.partner.id)),center)
                ws1.write(row,col+3,str(invoice.partner.name),center)
                if invoice.invoice_id.move_type=='in_invoice':
                    ws1.write(row,col+4,str(invoice.invoice_number),center)
                else:
                    ws1.write(row,col+4,'')
                ws1.write(row,col+5,str(invoice.invoice_ctrl_number),center)
                if invoice.invoice_id.move_type=='in_receipt':
                    ws1.write(row,col+6,str(invoice.invoice_number),center)
                else:
                    ws1.write(row,col+6,'')
                if invoice.invoice_id.move_type=='in_refund':
                    ws1.write(row,col+7,str(invoice.invoice_number),center)
                else:
                    ws1.write(row,col+7,'')
                if invoice.tipo_doc == '01':
                    ws1.write(row,col+8,str(invoice.tipo_doc)+'-Registro',center)
                else:
                    ws1.write(row,col+8,str(invoice.tipo_doc)+'-Anulación',center)
                if invoice.invoice_id.move_type in ('in_refund','in_receipt'):
                    ws1.write(row,col+9,str(invoice.ref),center)
                if invoice.vat_ret_id.state == 'posted':
                    ws1.write(row,col+10,str(invoice.formato_fecha2(invoice.vat_ret_id.voucher_delivery_date)),right)
                    ws1.write(row,col+11,invoice.vat_ret_id.name,right)
                ws1.write(row,col+12,invoice.float_format(invoice.sale_total),right)
                acum_compra_iva=acum_compra_iva+invoice.sale_total
                ws1.write(row,col+14,invoice.float_format(invoice.total_exento),right)
                acum_exento=acum_exento+invoice.total_exento

                ###############
                ws1.write(row,col+16,invoice.float_format(invoice.base_general),right)
                acum_base_general=acum_base_general+invoice.base_general
                ws1.write(row,col+17,invoice.float_format(invoice.alicuota_general),right)
                acum_ali_general=acum_ali_general+invoice.alicuota_general
                ws1.write(row,col+18,invoice.float_format(invoice.base_reducida),right)
                acum_base_reducida=acum_base_reducida+invoice.base_reducida
                ws1.write(row,col+19,invoice.float_format(invoice.alicuota_reducida),right)
                acum_ali_reducida=acum_ali_reducida+invoice.alicuota_reducida

                ws1.write(row,col+20,invoice.float_format(invoice.base_adicional),right)
                acum_base_adicional=acum_base_adicional+invoice.base_adicional
                ws1.write(row,col+21,invoice.float_format(invoice.alicuota_adicional),right)
                acum_ali_adicional=acum_ali_adicional+invoice.alicuota_adicional
                if invoice.vat_ret_id.state == 'posted':
                    if invoice.invoice_id.move_type in ('out_refund','in_refund'):
                        sig=-1
                    else:
                        sig=1
                    ws1.write(row,col+22,invoice.float_format(sig*invoice.iva_retenido),right)
                    acum_retenidos=acum_retenidos+sig*invoice.iva_retenido
                else:
                    ws1.write(row,col+22,'0,00',right)
        row=row+1

        # Definimos una función de formato local o usamos la del wizard para evitar depender de 'invoice'
        def format_val(val):
            return self.float_format2(val) # Usamos el método que ya tienes en el wizard principal
            
        ws1.write_merge(row, row, 0, 11,  "TOTAL..:", header_content_style_negri)
        ws1.write(row,col+12,format_val(acum_compra_iva),header_content_style_negri)
        ws1.write(row,col+14,format_val(acum_exento),header_content_style_negri)

        ws1.write(row,col+16,format_val(acum_base_general),header_content_style_negri)
        ws1.write(row,col+17,format_val(acum_ali_general),header_content_style_negri)
        ws1.write(row,col+18,format_val(acum_base_reducida),header_content_style_negri)
        ws1.write(row,col+19,format_val(acum_ali_reducida),header_content_style_negri)
        ws1.write(row,col+20,format_val(acum_base_adicional),header_content_style_negri)
        ws1.write(row,col+21,format_val(acum_ali_adicional),header_content_style_negri)
        ws1.write(row,col+22,format_val(acum_retenidos),header_content_style_negri)

        row=row+3
        ws1.write_merge(row, row, col+1, col+3, "Resumen del Periódo", sub_header_style_l)
        ws1.write(row,col+4,'Base Imponible',center)
        ws1.write(row,col+5,'Crédito Fiscal',center)

        row=row+1
        ws1.write_merge(row, row, col+1, col+3, "Total de las Compras Internas solo afectadas en alícuota General", sub_header_style_l)
        ws1.write(row,col+4,format_val(acum_base_general),sub_header_style_r)
        ws1.write(row,col+5,format_val(acum_ali_general),sub_header_style_r)

        row=row+1
        #ws1.write(row,col+1,'Total de las Ventasinternas Afectadas en alícuota Reducida',center)
        ws1.write_merge(row, row, col+1, col+3, "Total de las Compras Internas Solo afectadas en alícuota Reducida", sub_header_style_l)
        ws1.write(row,col+4,format_val(acum_base_reducida),sub_header_style_r)
        ws1.write(row,col+5,format_val(acum_ali_reducida),sub_header_style_r)

        row=row+1
        ws1.write_merge(row, row, col+1, col+3, "Total de las Compras Internas solo afectadas en alícuota General + Adicional", sub_header_style_l)
        ws1.write(row,col+4,format_val(acum_base_adicional),sub_header_style_r)
        ws1.write(row,col+5,format_val(acum_ali_adicional),sub_header_style_r)

        row=row+1
        ws1.write_merge(row, row, col+1, col+3, "Totale Exentos Compras Internas", sub_header_style_l)
        ws1.write(row,col+4,format_val(acum_exento),sub_header_style_r)

        row=row+1
        ws1.write_merge(row, row, col+1, col+3, "Totales de las Compras no Sujeta", sub_header_style_l)
        ws1.write(row,col+4,"0,00",sub_header_style_r)

        row=row+1
        ws1.write_merge(row, row, col+1, col+3, "Total sin Derecho a Crédito IVA", sub_header_style_l)
        ws1.write(row,col+4,"0,00",sub_header_style_r)

        row=row+1
        ws1.write_merge(row, row, col+1, col+3, "Totales Generales", sub_header_style_l)
        ws1.write(row,col+5,format_val(acum_base_general+acum_ali_general+acum_base_reducida+acum_ali_reducida+acum_base_adicional+acum_ali_adicional),sub_header_style_r)

        row=row+1
        ws1.write_merge(row, row, col+1, col+3, "Créditos Fiscales Totalmente Deducible", sub_header_style_l)
        ws1.write(row,col+5,format_val(acum_ali_general+acum_ali_reducida+acum_ali_adicional),sub_header_style_r)

        row=row+1
        ws1.write_merge(row, row, col+1, col+3, "Total Crédito Fiscales Deducible", sub_header_style_l)
        ws1.write(row,col+5,format_val(acum_ali_general+acum_ali_reducida+acum_ali_adicional),sub_header_style_r)

        row=row+1
        ws1.write_merge(row, row, col+1, col+3, "IVA Retenido (al Vendedor)", sub_header_style_l)
        ws1.write(row,col+5,format_val(acum_retenidos),sub_header_style_r)
       

        wb1.save(fp)
        out = base64.encodebytes(fp.getvalue())
        fecha  = datetime.now().strftime('%d/%m/%Y') 
        self.write({'state': 'get', 'report': out, 'name':'Libro de compras '+ fecha+'.xls'})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.wizard.libro.compras',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }