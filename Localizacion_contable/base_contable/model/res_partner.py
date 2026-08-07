# -*- coding: utf-8 -*-

from odoo import fields, models, api
from odoo.exceptions import ValidationError
import re  # Importamos la librería de expresiones regulares de Python


class Partner(models.Model):
    _inherit = 'res.partner'

    contribuyente = fields.Selection([('no', 'No'), ('si', 'Si')], default="no")
    people_type = fields.Selection(string='People type', selection=[
        ('resident_nat_people', 'PNRE Persona Natural Residente'),
        ('non_resit_nat_people', 'PNNR Persona Natural no Residente'),
        ('domi_ledal_entity', 'PJDO Persona Jurídica Domiciliada'),
        ('legal_ent_not_domicilied', 'PJND Persona Jurídica no Domiciliada'),
    ], required=True)
    seniat_url = fields.Char(string='Dirección SENIAT', readonly=True, default="http://contribuyente.seniat.gob.ve/BuscaRif/BuscaRif.jsp")
    doc_tipo = fields.Selection([
        ('V', 'V'),
        ('E', 'E'),
        ('J', 'J'),
        ('G', 'G'),
        ('P', 'P'),
        ('C', 'C'),
    ])
    partner_type = fields.Selection([
        ('national', 'Nacional'),
        ('international', 'Internacional'),
    ], required=True, default='national')
    
    # Campo tipo Char para conservar ceros a la izquierda
    vat_aux = fields.Char(string='Número de Documento') 

    # Campo nativo computado
    vat = fields.Char(compute='_compute_vat', store=True, readonly=False)

    mobile = fields.Char(string='Teléfono Celular')

    @api.depends('doc_tipo', 'vat_aux')
    def _compute_vat(self):
        for partner in self:
            if partner.doc_tipo and partner.vat_aux:
                partner.vat = f"{partner.doc_tipo}-{partner.vat_aux}"
            elif partner.vat_aux:
                partner.vat = str(partner.vat_aux)
            else:
                partner.vat = False

    # --- NUEVA RESTRICCIÓN PARA VALIDAR EL CONTENIDO DE VAT_AUX ---
    @api.constrains('vat_aux')
    def _check_vat_aux_format(self):
        for partner in self:
            if partner.vat_aux:
                # Expresión regular: permite únicamente dígitos (0-9) y el guion (-)
                # ^[0-9-]+$ significa que todo el texto debe cumplir esa condición obligatoriamente
                if not re.match(r'^[0-9-]+$', partner.vat_aux):
                    raise ValidationError(
                        "El número del campo (Cedula/RIF) solo puede contener números y el carácter '-' (guion medios)."
                    )