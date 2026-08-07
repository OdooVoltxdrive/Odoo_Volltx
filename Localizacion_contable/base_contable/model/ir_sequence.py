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

class IrSequence(models.Model):
    _inherit = 'ir.sequence'

    aplique_doc = fields.Selection([('df', 'Nota de Credito,Debito, Facturas'),('oe', 'Orden de Entrega'),('sr','Sin Restrinción')],default='sr',string="Usar Secuencia solo en:")