# -*- coding: utf-8 -*-

import hashlib
import json
import logging
import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    # --- CAMPOS DE CONFIGURACIÓN DE UNIDIGITAL ---
    usar_fact_digi = fields.Boolean(default=False)
    unidg_environment = fields.Selection([
        ('demo', 'DEMO'),
        ('prod', 'PRODUCCIÓN'),
    ], string='Ambiente Unidigital', default='demo', required=True)

    # Campos para las credenciales de la Imprenta Digital
    enpoint = fields.Char(string="Endpoint autenticación", copy=False, default="/user/login")
    url = fields.Char(string="URL Base API", copy=False, default='https://qa.unidigital.global/digitalinvoice-core')
    unidg_api_user = fields.Char(string='Usuario API', default="siliconvalleyvzla@unidigital.global")
    unidg_api_password = fields.Char(string='Clave API', default="1VTYmLZs0,cKt8;1J67#")
    
    # Campo para almacenar el token JWT y respuestas
    unidg_jwt_token = fields.Char(string='Token JWT Actual', readonly=True, copy=False)
    unidg_token_expiry = fields.Char(string='Vigencia del Token', readonly=True, copy=False)
    codigo = fields.Char(readonly=True, copy=False)
    mensaje = fields.Char(readonly=True, copy=False)

    enpoint_emision = fields.Char(string="Endpoint Emisión", copy=False, default='/documents/createandapprove')
    endpoint_pdf_doc = fields.Char(string="Endpoint vista Documentos", default="/documents/view")
    enpoint_ultimo_doc = fields.Char(string="Endpoint Último Documento", copy=False)
    seriestrongid = fields.Char(string="SerieStrOngid",copy=False,readonly=True) 
    sucursal_strong_id = fields.Char(string="SucursalStrongId",copy=False, default="81e836fe-eff1-4ca7-bcfd-5f079a44a503")


    def unidg_get_token(self):
        """Genera el hash SHA-512 de la contraseña y solicita el Token JWT + SerieStrongId a Unidigital."""
        for company in self:
            if not company.url or not company.enpoint or not company.unidg_api_user or not company.unidg_api_password:
                raise UserError(_("Por favor, complete todas las credenciales antes de validar el token."))

            base_url = company.url.strip().rstrip('/')
            endpoint = company.enpoint.strip()
            if not endpoint.startswith('/'):
                endpoint = '/' + endpoint
            full_url = f"{base_url}{endpoint}"

            raw_password = company.unidg_api_password.encode('utf-8')
            password_sha512 = hashlib.sha512(raw_password).hexdigest()

            payload = {
                "username": company.unidg_api_user.strip(),
                "password": password_sha512
            }
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }

            try:
                _logger.info("Unidigital: Peticion de Login a %s", full_url)
                response = requests.post(full_url, data=json.dumps(payload), headers=headers, timeout=15)
                
                company.codigo = str(response.status_code)

                if response.status_code in (200, 201):
                    res_data = response.json()
                    
                    token = res_data.get("accessToken") or res_data.get("token")
                    
                    # Extraer el strongId del primer elemento de "series"
                    series = res_data.get("series", [])
                    strong_id = False
                    if series and isinstance(series, list) and len(series) > 0:
                        strong_id = series[0].get("strongId")
                    
                    if token:
                        company.unidg_jwt_token = token
                        company.seriestrongid = strong_id
                        company.mensaje = _("Conexión Exitosa. Token y Serie cargados correctamente.")
                        _logger.info("Unidigital: Token y SerieStrongId actualizados exitosamente.")
                    else:
                        company.mensaje = _("Respuesta exitosa pero no se encontró 'accessToken'.")
                else:
                    company.unidg_jwt_token = False
                    company.seriestrongid = False
                    company.mensaje = f"Error {response.status_code}: {response.text}"

            except requests.exceptions.RequestException as e:
                company.codigo = "ERR_NET"
                company.unidg_jwt_token = False
                company.seriestrongid = False
                company.mensaje = f"Error de conexión: {str(e)}"

    def limpia(self):
        """Limpia los campos de estado y token."""
        for company in self:
            company.codigo = ''
            company.mensaje = ''
            company.unidg_jwt_token = ''
            company.unidg_token_expiry = ''
            company.seriestrongid = ''