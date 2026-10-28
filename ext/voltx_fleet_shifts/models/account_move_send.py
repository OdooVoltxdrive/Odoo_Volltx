# -*- coding: utf-8 -*-
import base64
import requests
import logging
from odoo import models

_logger = logging.getLogger(__name__)


class AccountMoveSend(models.AbstractModel):
    _inherit = 'account.move.send'

    def _prepare_invoice_pdf_report(self, invoices_data, **kwargs):
        """
        Interrumpe la generación del reporte QWeb nativo si la factura
        proviene de Unidigital y adjunta directamente el binario descargado.
        """
        # Ejecuta la llamada nativa pasando los argumentos exactos
        res = super()._prepare_invoice_pdf_report(invoices_data, **kwargs)

        for invoice, invoice_data in invoices_data.items():
            # Validamos que la empresa use digital y que la factura tenga resultado (UUID/ID)
            if not invoice.company_id.usar_fact_digi or not invoice.result:
                continue

            clean_result = str(invoice.result).strip('"\'' ).strip()
            if not clean_result:
                continue

            base_url = (invoice.company_id.url or '').strip().rstrip('/')
            endpoint = (invoice.company_id.endpoint_pdf_doc or '').strip().strip('/')
            pdf_url = f"{base_url}/{endpoint}/{clean_result}"

            try:
                # Descargamos el binario del PDF generado por la imprenta digital
                response = requests.get(pdf_url, timeout=15)
                if response.status_code == 200 and response.content:
                    # Sobrescribimos el contenido del PDF en el diccionario que usa el wizard
                    invoice_data['pdf_attachment_values'] = {
                        'name': f"{invoice.name.replace('/', '_')}_fiscal.pdf",
                        'raw': response.content,
                        'mimetype': 'application/pdf',
                        'res_model': 'account.move',
                        'res_id': invoice.id,
                    }
                    _logger.info("Unidigital: PDF descargado y asignado para %s", invoice.name)
            except Exception as e:
                _logger.error("Unidigital: No se pudo descargar el PDF de %s: %s", invoice.name, str(e))

        return res