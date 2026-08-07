# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import timedelta, date, datetime
from odoo.exceptions import UserError

from pytz import timezone
from bs4 import BeautifulSoup
import requests
import urllib3
urllib3.disable_warnings()

# Moneda..
class CurrencyRate(models.Model):
    _inherit = "res.currency.rate"

    # _sql_constraints = [('unique_name', 'CHECK(1=1)', 'Only one currency rate per day allowed!')]
    _sql_constraints = [('unique_name', 'CHECK(1=1)', 'Only one currency rate per day allowed!')]
    # currency_id = fields.Many2one('res.currency',readonly=False,copied=False)


    @api.model_create_multi
    def create(self, vals_list):
        """
        Sobreescribe el método create para evitar la creación de tasas con fecha anterior a la actual.
        El campo de fecha en el modelo res.currency.rate se llama 'name'.
        Adaptado a Odoo 19 utilizando vals_list para el manejo multi-registro del ORM.
        """
        # 1. Iteramos la lista de diccionarios que recibe Odoo 19
        for vals in vals_list:
            # Obtener la fecha de la nueva tasa.
            # En res.currency.rate, el campo fecha se llama 'name' y es un DateField.
            rate_date_str = vals.get('name') 
            
            if rate_date_str:
                # Odoo puede enviar un objeto date/datetime o un string. Nos aseguramos de procesarlo como Date.
                if isinstance(rate_date_str, (date, datetime)):
                    rate_date = rate_date_str.date() if isinstance(rate_date_str, datetime) else rate_date_str
                else:
                    rate_date = fields.Date.from_string(rate_date_str)
                    
                today = date.today()
                
                # 2. Realizar la validación
                if rate_date < today:
                    # Si la fecha de la tasa es menor que la fecha actual (retroactiva), lanza el error.
                    raise UserError(
                        "❌ ¡Creación de Tasa Rechazada! "
                        "No se permite crear tipos de cambio con fecha anterior a la fecha actual."
                    )

        # 3. Si pasa la validación en todos los registros, llama al método original enviando la lista completa
        return super().create(vals_list)



    # Nuevo método: Evitar modificar a una fecha anterior
    def write(self, vals):
        """
        Sobreescribe el método write para evitar que se cambie la fecha ('name') 
        de un registro a una fecha anterior a la que ya tenía.
        """
        # Solo necesitamos ejecutar la lógica si se está intentando modificar el campo 'name' (fecha)
        if 'name' in vals:
            if isinstance(vals['name'], (date, datetime)):
                new_date = vals['name'].date() if isinstance(vals['name'], datetime) else vals['name']
            else:
                new_date = fields.Date.from_string(vals['name'])
            
            for record in self:
                # 1. Obtener la fecha actual del registro
                old_date = record.name
                
                # 2. Realizar la validación
                # Si la nueva fecha es anterior a la fecha original del registro, se rechaza
                if old_date and new_date < old_date:
                    raise UserError(
                        "❌ ¡Modificación de Tasa Rechazada! "
                        "No se puede cambiar la fecha de una tasa de cambio a una fecha anterior. "
                    )

        # 2. Validación de inverse_company_rate
        if 'inverse_company_rate' in vals:
            raise UserError(
                "❌ ¡Modificación de Tasa Rechazada! "
                "El campo 'Tasa Inversa' no puede ser modificado manualmente. Es un campo calculado."
            )

        # 3. Si pasa la validación (o si el campo 'name' no se modificó), se realiza la escritura
        return super().write(vals)




    def central_bank(self):
        url = "https://www.bcv.org.ve/"
        req = requests.get(url, verify=False)
        active_euro = False

        status_code = req.status_code
        if status_code == 200:

            html = BeautifulSoup(req.text, "html.parser")
            # Dolar
            dolar_container = html.find('div', {'id': 'dolar'})
            # Usamos .text para obtener solo el número y .strip() para limpiar espacios
            dolar_valor = dolar_container.find('strong').text.strip()
            # Quitamos el punto de miles y cambiamos la coma decimal por punto
            dolar = float(dolar_valor.replace('.', '').replace(',', '.'))
            # Euro
            euro_container = html.find('div', {'id': 'euro'})
            euro_valor = euro_container.find('strong').text.strip()
            euro = float(euro_valor.replace('.', '').replace(',', '.'))

            if self.currency_id.name == 'USD':
                bcv = dolar
            elif self.currency_id.name == 'EUR':
                bcv = euro
            else:
                bcv = False
            id_usd = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
            id_euro = self.env['res.currency'].search([('name', '=', 'EUR')], limit=1)
            if id_euro:
                active_euro = True
            # raise UserError(_("valor usd=%s valor euro=%s")%(id_usd,id_euro)) 

            lista = self.env['res.company'].search([])
            # for det in lista:
            ## dolar=60
            vals = {
                # 'hora':datetime.now(),
                'name': datetime.now(),
                'inverse_company_rate': dolar,
                'currency_id': id_usd.id,
                'company_rate': 1 / dolar if dolar else 0,
                'company_id': '',  # det.id, #self.env.company.id #det.id,
            }
            # Se envuelven los valores en una lista [] para cumplir de forma segura con api.model_create_multi
            self.create([vals])
            
            if active_euro == True:
                vals2 = {
                    # 'hora':datetime.now(),
                    'name': datetime.now(),
                    'inverse_company_rate': euro,
                    'currency_id': id_euro.id,
                    'company_rate': 1 / euro if euro else 0,
                    'company_id': '',  # det.id, #self.env.company.id #det.id,
                }
                # Se envuelven los valores en una lista [] para cumplir de forma segura con api.model_create_multi
                self.create([vals2])
                
            self.funcion_actualiza_coste_precio_venta()

            

    def funcion_actualiza_coste_precio_venta(self):
        lista2 = self.env['product.product'].search([])
        if lista2:
            for item in lista2:
                item.actualiza_coste()
                item.actualiza_precio_venta_bs()

        lista = self.env['product.template'].search([])
        if lista:
            for rec in lista:
                rec.actualiza_coste()
                rec.actualiza_precio_venta_bs()