# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError, AccessError
from odoo.tools import float_compare, date_utils
from odoo.tools.misc import formatLang, format_date
from contextlib import ExitStack, contextmanager

from datetime import date, timedelta
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

#forbidden fields
INTEGRITY_HASH_MOVE_FIELDS = ('date', 'journal_id', 'company_id')
INTEGRITY_HASH_LINE_FIELDS = ('debit', 'credit', 'account_id', 'partner_id')
#_logger = logging.getLogger('__name__')


class StockPicking(models.Model):
    _inherit = 'stock.picking'

  
    def button_validate(self):
        res=super().button_validate()
        for line in self.move_line_ids:
            self.actualiza_costo_usd_stock_layer(line.product_id)
            self.actualiza_costo_usd(line.product_id)
        #self._calculate_average_cost_usd()
        return res


    def _calculate_average_cost_usd(self):

        # Obtener todos los productos relacionados con el picking

        for picking in self:

            for move in picking.move_line_ids:

                product = move.product_id

                # Obtener todas las capas de valoración para el producto

                valuation_layers = self.env['stock.valuation.layer'].search([

                ('product_id', '=', product.id)

                ])

                # Calcular el costo promedio en dólares

                total_value_usd = sum(layer.value_usd for layer in valuation_layers)

                total_quantity = sum(layer.quantity for layer in valuation_layers)

                if total_quantity > 0:

                    average_cost_usd = total_value_usd / total_quantity

                else:

                    average_cost_usd = 0.0

                product.standard_price_usd = average_cost_usd



    def actualiza_costo_usd_stock_layer(self,product_id):
    	for record in self:
	        busca_move=record.env['stock.move'].search([('picking_id','=',record.id),('product_id','=',product_id.id)],limit=1)
	        if busca_move:
	            busca_layer=record.env['stock.valuation.layer'].search([('stock_move_id','=',busca_move.id),('product_id','=',product_id.id)],limit=1)
	            if busca_layer:
	                busca_layer.value_usd=record.actualiza_valoracion_usd(product_id)
	                busca_layer.x_tasa=record.registra_tasa(product_id)
                


    def registra_tasa(self,product_id):
        value=1
        if not self.sale_id:
            busca_purchase=self.env['purchase.order'].search([('name','=',self.origin)],limit=1)
            if busca_purchase:
                for line in busca_purchase.order_line.search([('product_id','=',product_id.id),('order_id','=',busca_purchase.id)]):
                    value=line.order_id.x_tasa
        else:
            value=self.sale_id.x_tasa
        return value



    def actualiza_valoracion_usd(self,product_id):
        value=1
        if not self.sale_id:
            busca_purchase=self.env['purchase.order'].search([('name','=',self.origin)],limit=1)
            if busca_purchase:
                for line in busca_purchase.order_line.search([('product_id','=',product_id.id),('order_id','=',busca_purchase.id)]):
                    if line.order_id.currency_id!=self.env.company.currency_id:
                        value=line.product_qty*line.price_unit
                    else:
                        value=(line.product_qty*line.price_unit)/line.order_id.x_tasa
        else:
            for line in self.sale_id.order_line.search([('product_id','=',product_id.id),('order_id','=',self.sale_id.id)]):
                value=-1*line.product_uom_qty*product_id.standard_price_usd
                """if line.order_id.currency_id!=self.env.company.currency_id:
                    value=-1*line.product_uom_qty*line.price_unit
                else:
                    value=-1*((line.product_uom_qty*line.price_unit)/line.order_id.x_tasa)"""
        return value


 ###############################################################

    def actualiza_costo_usd(self,product_id):
        busca=self.env['product.product'].search([('id','=',product_id.id)])
        if busca:
            for det in busca:
                result=self.calcula_costo_usd_prod(product_id)
                if result!=0:
                    det.standard_price_usd=abs(result)
                    det.product_tmpl_id.standard_price_usd=abs(result)

    def calcula_costo_usd_prod(self,product_id):
        lista=self.env['stock.valuation.layer'].search([('product_id','=',product_id.id)])
        costo_usd=total_usd=total_cantidad=0
        if lista:
            for det in lista:
                if det.quantity!=0:
                    total_usd=total_usd+det.value_usd
                    total_cantidad=total_cantidad+det.quantity
            costo_usd=total_usd/total_cantidad if total_cantidad!=0 else 0
        return costo_usd