# -*- coding: utf-8 -*-
import base64
import logging
import requests
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    unidigital_pdf_attachment_id = fields.Many2one(
        'ir.attachment',
        string="PDF Fiscal Unidigital",
        copy=False,
        help="Archivo PDF fiscal oficial retornado por la imprenta digital."
    )

    def _get_unidigital_pdf_url(self):
        """Construye la URL de consulta/descarga del documento fiscal."""
        self.ensure_one()
        if not getattr(self, 'result', False):
            return False

        clean_result = str(self.result).strip('\"\'').strip()
        if not clean_result:
            return False

        base_url = (self.company_id.url or '').strip().rstrip('/')
        endpoint = (getattr(self.company_id, 'endpoint_pdf_doc', '') or '').strip()
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint

        return f"{base_url}{endpoint}/{clean_result}"

    def action_download_unidigital_pdf(self):
        """Descarga el PDF desde la API de Unidigital y lo almacena en ir.attachment."""
        self.ensure_one()
        pdf_url = self._get_unidigital_pdf_url()
        if not pdf_url:
            return False

        company = self.company_id
        if not company.unidg_jwt_token and hasattr(company, 'unidg_get_token'):
            company.unidg_get_token()

        headers = {
            "Authorization": f"Bearer {company.unidg_jwt_token}",
            "Accept": "application/pdf, application/json, */*"
        }

        try:
            _logger.info("VoltX: Descargando PDF fiscal para factura %s desde %s", self.name, pdf_url)
            response = requests.get(pdf_url, headers=headers, timeout=25)

            # Si el token expiró, refrescar y reintentar
            if response.status_code == 401 and hasattr(company, 'unidg_get_token'):
                company.unidg_get_token()
                headers["Authorization"] = f"Bearer {company.unidg_jwt_token}"
                response = requests.get(pdf_url, headers=headers, timeout=25)

            if response.status_code == 200 and response.content:
                filename = f"Factura_Fiscal_{self.name.replace('/', '_')}.pdf"

                attachment = self.env['ir.attachment'].search([
                    ('res_model', '=', self._name),
                    ('res_id', '=', self.id),
                    ('name', '=', filename)
                ], limit=1)

                vals = {
                    'name': filename,
                    'type': 'binary',
                    'datas': base64.b64encode(response.content),
                    'res_model': self._name,
                    'res_id': self.id,
                    'mimetype': 'application/pdf',
                }

                if attachment:
                    attachment.write(vals)
                else:
                    attachment = self.env['ir.attachment'].create(vals)

                self.unidigital_pdf_attachment_id = attachment.id
                _logger.info("VoltX: Adjunto PDF fiscal vinculado con éxito ID %s", attachment.id)
                return attachment
            else:
                _logger.warning("VoltX: No se pudo descargar el PDF fiscal. Status: %s", response.status_code)
        except Exception as e:
            _logger.error("VoltX: Error al conectar con Unidigital para descargar PDF: %s", str(e))

        return False

    def confirmar2(self):
        """Sobrescribe la confirmación para descargar el PDF al completarse el posteo."""
        res = super().confirmar2()
        for rec in self:
            if rec.company_id.usar_fact_digi and rec.code == '200' and rec.state == 'posted':
                rec.action_download_unidigital_pdf()
        return res

    def action_invoice_sent(self):
        """Asegura que el PDF fiscal esté adjunto al abrir el asistente tradicional de correo."""
        self.ensure_one()
        if self.company_id.usar_fact_digi and not self.unidigital_pdf_attachment_id:
            self.action_download_unidigital_pdf()

        res = super().action_invoice_sent()

        if self.company_id.usar_fact_digi and self.unidigital_pdf_attachment_id:
            context = dict(res.get('context', {}))
            att_ids = list(context.get('default_attachment_ids', []))
            if self.unidigital_pdf_attachment_id.id not in att_ids:
                att_ids.append(self.unidigital_pdf_attachment_id.id)
            context['default_attachment_ids'] = att_ids
            res['context'] = context

        return res