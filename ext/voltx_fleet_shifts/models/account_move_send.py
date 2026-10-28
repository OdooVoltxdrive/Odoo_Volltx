# -*- coding: utf-8 -*-
from odoo import models


class AccountMoveSend(models.AbstractModel):
    _inherit = 'account.move.send'

    def _prepare_invoice_pdf_report(self, invoice, invoice_data):
        """
        Reemplaza la generación del reporte QWeb estándar de Odoo por el
        archivo PDF oficial descargado de Unidigital.
        """
        if getattr(invoice.company_id, 'usar_fact_digi', False):
            attachment = invoice.unidigital_pdf_attachment_id or invoice.action_download_unidigital_pdf()
            if attachment:
                invoice_data['invoice_pdf_attachment'] = attachment
                return

        return super()._prepare_invoice_pdf_report(invoice, invoice_data)