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

class AccountMove(models.Model):
    _inherit = 'account.move'

    hab_direc_enttrega=fields.Boolean(string='Hab. Direección', default=False)
    direccion_entrega=fields.Char(string='Direección de Entrega')
    sucursal = fields.Char(default='----------')

    
    """def fact_afectada_org(self,refe):
        lista=self.env['account.move'].search([('invoice_number_next', '=',self.fact_afect),('move_type','=','out_invoice'),('partner_id','=',self.partner_id.id)],limit=1)
        if lista:
            result=" "+str(lista.invoice_number_next)
            result=result+", Fecha: "+str(self.formato_fecha(lista.invoice_date))
            result=result+", Monto Fact: "+str(self.float_format(lista.amount_total_signed))
            result=result+" "+lista.company_id.currency_id.symbol
            return result
        else:
            return False"""


    def fact_afectada(self,refe):
        lista=self.env['account.move'].search([('invoice_number_next', '=',self.fact_afect),('move_type','=','out_invoice'),('partner_id','=',self.partner_id.id)],limit=1)
        if lista:
            if lista.company_id.currency_id==lista.currency_id:
                factor=1
            else:
                factor=lista.tasa
            result=" "+str(lista.invoice_number_next)
            result=result+", Fecha: "+str(self.formato_fecha(lista.invoice_date))
            result=result+", Monto Fact: "+str(self.float_format(lista.amount_total*factor))
            result=result+" "+lista.company_id.currency_id.symbol
            return result
        else:
            return False



    def formato_libre(self):
        if self.currency_id==self.company_id.currency_id:
            return self.env.ref('extension_formato_factura.action_formato_libre_report_somofi_bs').report_action(self)
        else:
            pass
            #return self.env.ref('extension_formato_factura.action_formato_libre_report_somofi').report_action(self)

    def ocultar_hablador(self):
        if self.moneda_doc=='a':
            valor='si'
        if self.moneda_doc=='b':
            if self.currency_id==self.company_id.currency_id:
                valor='si'
            else:
                valor='no'
        return valor

    def descuento(self):
        total_descu=0
        for det in self.invoice_line_ids:
            total_descu=total_descu+(det.price_unit*det.quantity-det.price_subtotal)
        return total_descu


    def doc_cedula(self,aux):
        #nro_doc=self.partner_id.vat
        busca_partner = self.env['res.partner'].search([('id','=',aux)])
        for det in busca_partner:
            tipo_doc=busca_partner.doc_tipo
            if busca_partner.vat:
                nro_doc=str(busca_partner.vat)
            else:
                nro_doc="00000000"
            tipo_doc=busca_partner.doc_tipo
        resultado=str(tipo_doc)+"-"+str(nro_doc)
        return resultado

    def formato_fecha(self,date):
        if date:
            fecha = str(date)
            fecha_aux=fecha
            ano=fecha_aux[0:4]
            mes=fecha[5:7]
            dia=fecha[8:10]  
            resultado=dia+"/"+mes+"/"+ano
        else:
            resultado="01-01-1900"
        return resultado

    def base_igtf_usd(self):
        valor=0
        if self.igtf_ids:
            for item in self.igtf_ids:
                if item.monto_ret_bs!=0:
                    valor=valor+item.monta_a_pagar
        if not self.igtf_ids and self.company_id.currency_id.id!=self.currency_id.id:
            valor=self.amount_base_imponible+self.amount_exento+self.amount_ivag+self.amount_ivar+self.amount_ivaa
        return round(valor,2)


    def equivalente_bs(self,valor):
        if self.currency_id.id==self.company_id.currency_id.id:
            factor=1
        else:
            factor=self.tasa
        valor=valor*factor
        return round(valor,4)

    def equivalente_usd(self,valor):
        if self.currency_id.id!=self.company_id.currency_id.id:
            factor=1
        else:
            factor=self.tasa
        valor=valor/factor
        return round(valor,4)


    def equivalente_fijo(self,valor):
        if self.moneda_doc=='b':
            if self.currency_id.id!=self.company_id.currency_id.id:
                factor=self.tasa
            else:
                factor=1
            valor=valor*factor
        if self.moneda_doc=='a':
            valor=valor
        return round(valor,2)

    def moneda(self):
        if self.moneda_doc=='a':
            moneda=self.company_id.currency_id.symbol
        if self.moneda_doc=='b':
            moneda=self.currency_id.symbol
        return moneda


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


    def valor_igtf_hablador(self):
        suma=0
        if self.igtf_ids:
            for det in self.igtf_ids:
                if det.moneda.id!=self.currency_id.id:
                    suma=suma+det.monto_ret_bs/det.tasa
        return suma

    def base_igtf_hablador(self):
        suma=0
        if self.igtf_ids:
            for det in self.igtf_ids:
                if det.moneda.id!=self.currency_id.id:
                    suma=suma+det.monta_a_pagar
        return suma

    def base_imp_16(self):
        suma=0
        if self.currency_id.id!=self.company_id.currency_id.id:
            factor=round(self.tasa,2)
        else:
            factor=1
        if self.invoice_line_ids:
            for rec in self.invoice_line_ids:
                if rec.tax_ids.aliquot=='general':
                    suma=suma+rec.price_subtotal
        suma=suma*factor
        return suma

    def base_igtf(self):
        suma=0
        if self.igtf_ids:
            for det in self.igtf_ids:
                if det.moneda.id!=self.currency_id.id:
                    suma=suma+det.monta_a_pagar_bs
        return suma

    def condicion_pago(self,valor):
        if valor=='cred':
            texto='Crédito'
        else:
            texto='Contado'
        return texto

    def get_literal_amount(self,amount):
        indicador = [("",""),("MIL","MIL"),("MILLON","MILLONES"),("MIL","MIL"),("BILLON","BILLONES")]
        entero = int(amount)
        decimal = int(round((amount - entero)*100))
        contador = 0
        numero_letras = ""
        while entero >0:
            a = entero % 1000
            if contador == 0:
                en_letras = self.convierte_cifra(a,1).strip()
            else:
                en_letras = self.convierte_cifra(a,0).strip()
            if a==0:
                numero_letras = en_letras+" "+numero_letras
            elif a==1:
                if contador in (1,3):
                    numero_letras = indicador[contador][0]+" "+numero_letras
                else:
                    numero_letras = en_letras+" "+indicador[contador][0]+" "+numero_letras
            else:
                numero_letras = en_letras+" "+indicador[contador][1]+" "+numero_letras
            numero_letras = numero_letras.strip()
            contador = contador + 1
            entero = int(entero / 1000)
        numero_letras = numero_letras+" Bolivares con " + str(decimal) +"/100"
        print('numero: ',amount)
        print(numero_letras)
        return numero_letras
        
    def convierte_cifra(self, numero, sw):
        lista_centana = ["",("CIEN","CIENTO"),"DOSCIENTOS","TRESCIENTOS","CUATROCIENTOS","QUINIENTOS","SEISCIENTOS","SETECIENTOS","OCHOCIENTOS","NOVECIENTOS"]
        lista_decena =  ["",("DIEZ","ONCE","DOCE","TRECE","CATORCE","QUINCE","DIECISEIS","DIECISIETE","DIECIOCHO","DIECINUEVE"),
                        ("VEINTE","VEINTI"),("TREINTA","TREINTA Y "),("CUARENTA" , "CUARENTA Y "),
                        ("CINCUENTA" , "CINCUENTA Y "),("SESENTA" , "SESENTA Y "),
                        ("SETENTA" , "SETENTA Y "),("OCHENTA" , "OCHENTA Y "),
                        ("NOVENTA" , "NOVENTA Y ")
                        ]
        lista_unidad = ["",("UN" , "UNO"),"DOS","TRES","CUATRO","CINCO","SEIS","SIETE","OCHO","NUEVE"]
        centena = int (numero / 100)
        decena = int((numero -(centena * 100))/10)
        unidad = int(numero - (centena * 100 + decena * 10))
        
        texto_centena = ""
        texto_decena = ""
        texto_unidad = ""
        
        #Validad las centenas
        texto_centena = lista_centana[centena]
        if centena == 1:
            if (decena + unidad)!=0:
                texto_centena = texto_centena[1]
            else:
                texto_centena = texto_centena[0]
        
        #Valida las decenas
        texto_decena = lista_decena[decena]
        if decena == 1:
            texto_decena = texto_decena[unidad]
        elif decena > 1:
            if unidad != 0:
                texto_decena = texto_decena[1]
            else:
                texto_decena = texto_decena[0]
        
        #Validar las unidades
        if decena != 1:
            texto_unidad = lista_unidad[unidad]
            if unidad == 1:
                texto_unidad = texto_unidad[sw]
        
        return "%s %s %s" %(texto_centena,texto_decena,texto_unidad)

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def equivalente_bs(self,valor):
        if self.move_id.currency_id.id==self.move_id.company_id.currency_id.id:
            factor=1
        else:
            factor=self.move_id.tasa
        valor=valor*factor
        return round(valor,4)

    def equivalente_usd(self,valor):
        if self.move_id.currency_id.id!=self.move_id.company_id.currency_id.id:
            factor=1
        else:
            factor=self.move_id.tasa
        valor=valor/factor
        return round(valor,4)

    def und_presentacion(self,product_tmpl_id):
        if product_tmpl_id.presentacion:
            medida=product_tmpl_id.presentacion.name
        else:
            medida='Unid.'
        return medida


    def vista_espacio(self,valor):
        result=valor
        #result = result.replace(' ','_')
        return result

    def formato_fecha(self):
        fecha = str(self.invoice_id.invoice_date)
        fecha_aux=fecha
        ano=fecha_aux[0:4]
        mes=fecha[5:7]
        dia=fecha[8:10]  
        resultado=dia+"/"+mes+"/"+ano
        return resultado


    


    def float_format(self,valor):
        if valor:
            result = '{:,.2f}'.format(valor)
            result = result.replace(',','*')
            result = result.replace('.',',')
            result = result.replace('*','.')
        else:
            result = "0,00"
        return result