# -*- coding: utf-8 -*-

import logging
import requests
import json
from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class RetentionVatIslr(models.Model):
    """Integración con API Unidigital para Comprobantes de Retención de ISLR SENIAT."""
    _inherit = 'isrl.retention'

    result = fields.Char(copy=False)
    hasErrors = fields.Char(copy=False)
    errorMessage = fields.Text(copy=False)
    information = fields.Char(copy=False)
    json_enviado = fields.Text(string="JSON Enviado", copy=False)
    code = fields.Char(copy=False, string="Código de respuesta servidor API")
    message = fields.Text(copy=False)
    state = fields.Selection(
        selection_add=[
            ('sent', 'Publicado y enviado'),
        ],
        ondelete={'sent': 'set default'}
    )

    def comprobante_sv(self):
        """
        Abre en una nueva pestaña la URL de consulta de la factura digital 
        construida a partir de la respuesta de Unidigital guardada en 'result'.
        """
        self.ensure_one()

        if not self.company_id.usar_fact_digi:
            raise UserError(_("Esta compañía no tiene habilitada la factura digital."))

        if not self.result:
            raise UserError(_("No hay un identificador de documento fiscal recibido de la imprenta digital."))

        # Limpia comillas dobles o espacios adicionales del valor guardado en self.result
        clean_result = str(self.result).strip('"\'' ).strip()

        if not clean_result:
            raise UserError(_("El código de documento fiscal no es válido."))

        # Construir la URL concatenando la compañía, el endpoint y el UUID limpio
        base_url = (self.company_id.url or '').strip()
        endpoint = (self.company_id.endpoint_pdf_doc or '').strip()
        
        # Asegura que las barras diagonales (/) no se dupliquen o falten
        if not base_url.endswith('/') and not endpoint.startswith('/'):
            target_url = f"{base_url}/{endpoint}/{clean_result}"
        else:
            target_url = f"{base_url}{endpoint}/{clean_result}"

        return {
            'type': 'ir.actions.act_url',
            'url': target_url,
            'target': 'new',
        }

    def _prepare_unidigital_islr_json(self):
        """Construye el Payload plano para ISLR compatible con /createretention de Unidigital."""
        self.ensure_one()

        partner = self.partner_id
        if not partner.vat:
            raise UserError(_("El Partner %s no tiene un número de RIF/CÉDULA configurado.") % partner.name)

        invoice = self.invoice_id
        if not invoice:
            raise UserError(_("El comprobante de retención no tiene una factura asociada."))

        # 1. Limpieza y separación de RIF (Ejemplo: J-307048670 -> Code: J, Registry: 307048670)
        raw_vat = str(partner.vat).replace('-', '').replace(' ', '').upper()
        code_rif = raw_vat[0] if raw_vat[0].isalpha() else 'J'
        number_rif = raw_vat[1:] if raw_vat[0].isalpha() else raw_vat

        # 2. Dirección limpia (evitar espacios en blanco)
        raw_address = False
        if hasattr(self, 'get_address_partner'):
            raw_address = self.get_address_partner()
        if not raw_address:
            raw_address = partner.street or partner.contact_address or ""

        clean_address = str(raw_address).strip()
        final_address = clean_address if clean_address else "Caracas, Venezuela"

        # 3. Limpieza estricta de Teléfono (solo dígitos numéricos)
        raw_phone = partner.phone or partner.mobile or "02120000000"
        clean_phone = ''.join(filter(str.isdigit, str(raw_phone)))
        final_phone = clean_phone if len(clean_phone) >= 7 else "02120000000"

        # 4. Mapeo exacto de Tipo de Persona desde res.partner -> people_type
        perceiver_mapping = {
            'resident_nat_people': 'PN-RESIDENTE',
            'non_resit_nat_people': 'PN-NO-RESIDENTE',
            'domi_ledal_entity': 'PJ-DOMICILIADA',
            'legal_ent_not_domicilied': 'PJ-NO-DOMICILIADA',
        }
        perceiver_type = perceiver_mapping.get(getattr(partner, 'people_type', False), 'PJ-DOMICILIADA')

        # 5. Fecha de emisión en formato UTC ISO 8601
        target_date = self.date_isrl or fields.Date.today()
        emission_dt = datetime.combine(target_date, datetime.min.time()).strftime('%Y-%m-%dT%H:%M:%SZ')

        # 6. Líneas de ISLR
        islr_lines = []
        for line in self.lines_id:
            concept_code = str(line.code or '001').zfill(3)
            islr_lines.append({
                "ConceptCode": concept_code,
                "TaxBase": round(line.base, 2),
                "Total": round(invoice.amount_total, 2),
                "TaxPercent": round(line.cantidad, 2),
                "AmountRetained": round(line.total, 2),
                "SubtrahendPN": round(line.sustraendo, 2),
                "Extra": {}
            })

        # 7. Mapeo de documento retenido
        inv_date = invoice.invoice_date.strftime('%d/%m/%Y') if invoice.invoice_date else target_date.strftime('%d/%m/%Y')
        inv_number = invoice.name or self.invoice_number or "00000001"
        ctrl_number = getattr(invoice, 'nro_control', False) or getattr(invoice, 'l10n_ve_control_number', False) or "00-00000001"

        doc_type_map = {
            'out_invoice': 'FA',
            'in_invoice': 'FA',
            'out_refund': 'NC',
            'in_refund': 'NC',
        }
        doc_type = doc_type_map.get(invoice.move_type, 'FA')

        documents_payload = [{
            "EmissionDate": inv_date,
            "Number": inv_number,
            "DocumentType": doc_type,
            "Serie": "0",
            "ControlNumber": ctrl_number,
            "AffectedDocumentNumber": getattr(invoice, 'fact_afect', '') or "",
            "Currency": "VES",
            "ExemptAmount": 0.0,
            "Total": round(invoice.amount_total, 2),
            "IVA": [],
            "ISLR": islr_lines
        }]

        # Número de comprobante limpio (solo enteros para el campo Number)
        voucher_num_digits = ''.join(filter(str.isdigit, str(self.name or '')))
        numeric_voucher_number = int(voucher_num_digits[-8:]) if voucher_num_digits else self.id

        return {
            "DocumentType": "RR",
            "Number": numeric_voucher_number,
            "EmissionDateAndTime": emission_dt,
            "Name": partner.name or "",
            "FiscalRegistryCode": code_rif,
            "FiscalRegistry": number_rif,
            "Address": final_address,
            "Phone": final_phone,
            "EmailTo": partner.email or "comprobantes@dominio.com",
            "PerceiverType": perceiver_type,
            "TaxBase": round(self.amount_untaxed, 2),
            "TaxAmount": 0.0,
            "TotalIGTF": 0,
            "AmountRetained": round(self.vat_retentioned, 2),
            "SystemReference": self.name or f"RR-{self.id}",
            "Documents": documents_payload
        }

    def envia_comp_ret_islr(self):
        """Método invocado por el botón de la vista XML."""
        for rec in self:
            company = rec.company_id or self.env.company
            url = getattr(company, 'unidigital_retention_url', False) or 'https://qa.unidigital.global/digitalinvoice-core/documents/createretention'

            # 1. Obtener y refrescar el Token usando la misma lógica de IVA
            token = getattr(company, 'unidg_jwt_token', False)
            if not token and hasattr(company, 'unidg_get_token'):
                company.unidg_get_token()
                token = getattr(company, 'unidg_jwt_token', False)

            # 2. Generar el JSON a enviar
            payload_data = rec._prepare_unidigital_islr_json()
            json_payload = json.dumps(payload_data, indent=4, ensure_ascii=False)
            rec.json_enviado = json_payload

            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            if token:
                headers['Authorization'] = f"Bearer {token}"
            else:
                _logger.warning("ALERTA: No se pudo obtener el token Unidigital para la compañía %s", company.name)

            _logger.info("Enviando Retención ISLR Unidigital (ID %s): %s", rec.id, json_payload)

            try:
                response = requests.post(url, data=json_payload.encode('utf-8'), headers=headers, timeout=30)
                http_status = response.status_code

                try:
                    res_json = response.json() if response.content else {}
                except Exception:
                    res_json = {}

                _logger.info("Respuesta Unidigital ISLR (ID %s - Status %s): %s", rec.id, http_status, response.text)

                # 3. Mapeo de campos de estado
                rec.code = str(res_json.get("code") if res_json.get("code") is not None else http_status)
                rec.hasErrors = str(res_json.get("hasErrors", http_status not in (200, 201)))
                rec.result = json.dumps(res_json.get("result")) if res_json.get("result") is not None else str(res_json.get("result", ""))

                # 4. Extracción de mensajes y errores
                api_msg = ""
                errors_data = res_json.get("errors", [])

                if isinstance(errors_data, list) and len(errors_data) > 0:
                    first_err = errors_data[0]
                    if isinstance(first_err, dict):
                        # Caso errores anidados dentro de errors[0]['errors']
                        sub_errors = first_err.get("errors", [])
                        if isinstance(sub_errors, list) and len(sub_errors) > 0:
                            sub_msg_list = [e.get("errorMessage", "") for e in sub_errors if isinstance(e, dict) and e.get("errorMessage")]
                            if sub_msg_list:
                                api_msg = "\n".join(sub_msg_list)

                        if not api_msg:
                            api_msg = first_err.get("message") or ""

                if not api_msg:
                    api_msg = res_json.get("message") or response.text or f"Respuesta HTTP {http_status}"

                rec.message = str(api_msg)

                if errors_data:
                    rec.information = json.dumps(errors_data, indent=2, ensure_ascii=False)
                    rec.errorMessage = str(api_msg)
                else:
                    rec.information = json.dumps(res_json, indent=2, ensure_ascii=False)
                    rec.errorMessage = str(api_msg)
                    rec.result = json.dumps(res_json.get("result", {}))
                    rec.state='sent'

                # 5. Respuesta e interacción con la UI de Odoo
                if http_status in (200, 201) and not res_json.get("hasErrors"):
                    if hasattr(rec, 'state') and rec.state == 'draft' and hasattr(rec, 'action_post'):
                        rec.action_post()

                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Comprobante Enviado'),
                            'message': _('La retención de ISLR fue procesada exitosamente.'),
                            'type': 'success',
                            'sticky': False,
                        }
                    }
                else:
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Respuesta API (Status %s)') % http_status,
                            'message': rec.message,
                            'type': 'danger',
                            'sticky': True,
                        }
                    }

            except requests.exceptions.RequestException as e:
                rec.hasErrors = "True"
                rec.code = "500"
                rec.errorMessage = f"Error de conexión: {str(e)}"
                rec.message = f"Error de conexión: {str(e)}"
                rec.information = str(e)

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error de Conexión'),
                        'message': rec.errorMessage,
                        'type': 'danger',
                        'sticky': True,
                    }
                }