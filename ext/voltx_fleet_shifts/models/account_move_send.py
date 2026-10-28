# -*- coding: utf-8 -*-
import json
import logging
import requests
from odoo import models

_logger = logging.getLogger(__name__)


class AccountMoveSend(models.AbstractModel):
    _inherit = 'account.move.send'

    def _prepare_invoice_pdf_report(self, invoices_data, **kwargs):
        """
        Descarga el PDF directamente desde la URL de Unidigital
        y lo adjunta al envío de correo, omitiendo el PDF nativo de Odoo.
        """
        invoices_digital = self.env['account.move']

        for invoice, invoice_data in invoices_data.items():
            if not invoice.company_id.usar_fact_digi or not invoice.result:
                continue

            # 1. Extraer el UUID limpio de result (igual que en print_digital)
            raw_res = invoice.result
            clean_result = ""
            try:
                parsed_res = json.loads(raw_res)
                if isinstance(parsed_res, dict):
                    clean_result = str(parsed_res.get('id') or parsed_res.get('documentId') or '')
                else:
                    clean_result = str(parsed_res)
            except Exception:
                clean_result = str(raw_res)

            clean_result = clean_result.strip('"\'' ).strip()
            if not clean_result:
                continue

            # 2. Construir la URL exacta (la misma a la que te lleva el botón verde)
            base_url = (invoice.company_id.url or '').strip().rstrip('/')
            endpoint = (invoice.company_id.endpoint_pdf_doc or '').strip().strip('/')
            pdf_url = f"{base_url}/{endpoint}/{clean_result}"

            try:
                _logger.info("Unidigital: Descargando PDF fiscal para correo desde: %s", pdf_url)
                
                # Headers de descarga
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                    "Accept": "application/pdf, application/json, */*"
                }
                if invoice.company_id.unidg_jwt_token:
                    headers["Authorization"] = f"Bearer {invoice.company_id.unidg_jwt_token}"

                response = requests.get(pdf_url, headers=headers, timeout=25)

                if response.status_code == 200 and response.content:
                    file_name = f"{invoice.name.replace('/', '_')}_fiscal.pdf"

                    # 3. Guardar el PDF en los adjuntos de la factura (queda en el chatter)
                    attachment = self.env['ir.attachment'].create({
                        'name': file_name,
                        'raw': response.content,
                        'mimetype': 'application/pdf',
                        'res_model': 'account.move',
                        'res_id': invoice.id,
                        'type': 'binary',
                    })

                    # 4. Asignar el PDF al wizard de envío (reemplaza el PDF nativo de Odoo)
                    invoice_data['pdf_attachment_values'] = {
                        'name': file_name,
                        'raw': response.content,
                        'mimetype': 'application/pdf',
                        'res_model': 'account.move',
                        'res_id': invoice.id,
                    }

                    if 'attachment_ids' in invoice_data:
                        invoice_data['attachment_ids'] = list(set(invoice_data['attachment_ids'] + [attachment.id]))
                    else:
                        invoice_data['attachment_ids'] = [attachment.id]

                    invoices_digital |= invoice
                    _logger.info("Unidigital: PDF fiscal adjuntado con éxito a la factura %s", invoice.name)
                else:
                    _logger.warning("Unidigital: Código %s al descargar PDF desde %s", response.status_code, pdf_url)

            except Exception as e:
                _logger.error("Unidigital: Error descargando PDF de Unidigital: %s", str(e))

        # Para las facturas que no son de Unidigital, se ejecuta el flujo estándar de Odoo
        remaining_invoices_data = {
            inv: data for inv, data in invoices_data.items() if inv not in invoices_digital
        }

        if remaining_invoices_data:
            return super()._prepare_invoice_pdf_report(remaining_invoices_data, **kwargs)

        return invoices_data