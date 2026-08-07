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



class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'


    x_tasa = fields.Float(compute='_compute_tasa',store=True, readonly=False,digits=(12, 4))

    def button_confirm(self):
        """
        Valida que todas las líneas de la orden de compra con producto tengan 
        impuestos asignados antes de confirmar.
        """
        # 1. Llamamos a la función de validación
        self._validate_product_taxes_po()
        # 2. Si la validación pasa, llamamos al método original para confirmar
        res = super(PurchaseOrder, self).button_confirm()
        return res



    def _validate_product_taxes_po(self):
        """ Valida que todas las líneas de compra con producto tengan al menos un impuesto. """
        for order in self:
            # Buscamos líneas que tengan un producto asignado Y que no tengan impuestos (taxes_id es Many2many)
            lines_without_tax = order.order_line.filtered(
                lambda line: line.product_id and not line.tax_ids
            )
            
            if lines_without_tax:
                # Construimos un mensaje de error detallado
                product_names = ', '.join(lines_without_tax.mapped('product_id.display_name'))
                raise UserError(_(
                    "🛑 No se puede confirmar la Orden de Compra."
                    "\nLas siguientes líneas de producto no tienen impuestos de compra asignados:"
                    "\n%s"
                    "\n\nPor favor, asigne un impuesto (o alícuota) a cada producto e intente de nuevo."
                ) % product_names)



    @api.depends('date_order')
    @api.onchange('date_order')
    def _compute_tasa(self):
        result=1
        for selff in self:
            if selff.date_order:
                lista=selff.env['res.currency.rate'].search([('currency_id','=',selff.company_id.currency_sec_id.id),('name','<=',selff.date_order)],order='name desc',limit=1)
            if lista:
                result=lista.inverse_company_rate
            selff.x_tasa=result


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    @api.onchange('taxes_id')
    def impuestos_varios(self):
        cont=0
        tax_aux_id=0
        if self.taxes_id:
            for lista in self.taxes_id:
                cont=cont+1
            if cont>1:
                self.taxes_id = [(5, 0, 0)] # Borra todos los impuestos si no hay uno único



class SaleOrder(models.Model):
    _inherit = 'sale.order'


    x_tasa = fields.Float(compute='_compute_tasa',store=True, readonly=False,digits=(12, 4))



    @api.depends('date_order')
    @api.onchange('date_order')
    def _compute_tasa(self):
        result=1
        for selff in self:
            if selff.date_order:
                lista=selff.env['res.currency.rate'].search([('currency_id','=',selff.company_id.currency_sec_id.id),('name','<=',selff.date_order)],order='name desc',limit=1)
            if lista:
                result=lista.inverse_company_rate
            selff.x_tasa=result


    def action_confirm(self):
        """
        Valida que todas las líneas del pedido con producto tengan impuestos 
        antes de confirmar.
        """
        # 1. Llamamos a la función de validación
        self._validate_product_taxes_so()
        # 2. Si la validación pasa, llamamos al método original de Odoo para confirmar
        res = super(SaleOrder, self).action_confirm()
        return res


    def _validate_product_taxes_so(self):
        """ Valida que todas las líneas de pedidos con producto tengan al menos un impuesto asignado. """
        for order in self:
            # Buscamos líneas que tengan un producto asignado Y que no tengan impuestos (tax_id es Many2many)
            lines_without_tax = order.order_line.filtered(
                lambda line: line.product_id and not line.tax_ids
            )
            
            if lines_without_tax:
                # Construimos un mensaje de error detallado
                product_names = ', '.join(lines_without_tax.mapped('product_id.display_name'))
                raise UserError(_(
                    "🛑 No se puede confirmar el Pedido de Venta."
                    "\nLas siguientes líneas de producto no tienen impuestos de venta asignados:"
                    "\n%s"
                    "\n\nPor favor, asigne un impuesto (o alícuota) a cada producto e intente de nuevo."
                ) % product_names)



class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'


    @api.onchange('tax_id')
    def impuestos_varios(self):
        cont=0
        tax_aux_id=0
        if self.tax_id:
            for lista in self.tax_id:
                cont=cont+1
            if cont>1:
                self.tax_id = [(5, 0, 0)] # Borra todos los impuestos si no hay uno único

   