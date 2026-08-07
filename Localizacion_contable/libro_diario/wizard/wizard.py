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

class LibroComprasModelo(models.Model):
    _name = "libro.diario.wizard.pdf"

    fecha_desde=fields.Date()
    fecha_hasta=fields.Date()
    account_id=fields.Many2one('account.account')
    name=fields.Char()
    total_deber=fields.Float()
    total_haber=fields.Float()

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

class WizardReport_1(models.TransientModel): # aqui declaro las variables del wizar que se usaran para el filtro del pdf
    _name = 'wizard.libro.diario'
    _description = "Libro Diario"

    date_from  = fields.Date('Date From', default=lambda *a:(datetime.now() - timedelta(days=(1))).strftime('%Y-%m-%d'))
    date_to = fields.Date(string='Date To', default=lambda *a:datetime.now().strftime('%Y-%m-%d'))

    company_id = fields.Many2one('res.company','Company',default=lambda self: self.env.company.id)
    line  = fields.Many2many(comodel_name='libro.diario.wizard.pdf', string='Lineas')

    def rif(self,aux):
        #nro_doc=self.partner_id.vat
        busca_partner = self.env['res.partner'].search([('id','=',aux)])
        for det in busca_partner:
            tipo_doc=busca_partner.doc_tipo
            nro_doc=str(busca_partner.vat)
        resultado=str(tipo_doc)+"-"+str(nro_doc)
        return resultado

    def periodo(self,date):
        fecha = str(date)
        fecha_aux=fecha
        mes=fecha[5:7] 
        resultado=mes
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



    def print_libro_diario(self):
        t=self.env['libro.diario.wizard.pdf'].search([])
        w=self.env['wizard.libro.diario'].search([('id','!=',self.id)])
        t.unlink()
        w.unlink()
        cur_account=self.env['account.account'].search([],order="code asc")
        for det_account in cur_account:
            acum_deber=0
            acum_haber=0
            cursor = self.env['account.move.line'].search([('date', '>=', self.date_from),('date','<=',self.date_to),('account_id','=',det_account.id),('parent_state','=','posted'),('company_id','=',self.company_id.id)])
            """if cursor:
                raise UserError(_('cursor = %s')%cursor)"""
            if cursor:
                for det in cursor:
                    acum_deber=acum_deber+det.debit
                    acum_haber=acum_haber+det.credit
                #raise UserError(_('lista_mov_line = %s')%acum_deber)
                values=({
                    'account_id':det_account.id,
                    'total_deber':acum_deber,
                    'total_haber':acum_haber,
                    'name':det_account.name,
                    'fecha_desde':self.date_from,
                    'fecha_hasta':self.date_to,
                    })
                diario_id = t.create(values)
        self.line=self.env['libro.diario.wizard.pdf'].search([])
        return self.env.ref('libro_diario.action_libro_diario_report').report_action(self)