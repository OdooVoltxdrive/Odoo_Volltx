from odoo import models
import json

class AccountMove(models.Model):
    _inherit = 'account.move'

    def _get_share_url(self, redirect=False, signup_partner=False, pid=None):
        self.ensure_one()
        if self.company_id.usar_fact_digi and self.result:
            # Extraer el UUID limpio de result
            raw_res = self.result
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

            if clean_result:
                # Construir la URL de Unidigital
                base_url = (self.company_id.url or '').strip().rstrip('/')
                endpoint = (self.company_id.endpoint_pdf_doc or '').strip().strip('/')
                pdf_url = f"{base_url}/{endpoint}/{clean_result}"
                return pdf_url

        return super()._get_share_url(redirect=redirect, signup_partner=signup_partner, pid=pid)
