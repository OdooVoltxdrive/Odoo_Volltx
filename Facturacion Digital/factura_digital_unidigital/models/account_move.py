# -*- coding: utf-8 -*-

import json
import logging
import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    result = fields.Char(copy=False)
    hasErrors = fields.Char(copy=False)
    errorMessage = fields.Text(copy=False)
    information = fields.Char(copy=False)
    json_enviado = fields.Text(string="JSON Enviado", copy=False)
    proximo_doc = fields.Char(compute='_compute_proximo_valor')
    proximo_ctrl = fields.Char(compute='_compute_proximo_ctrl')
    code = fields.Char(copy=False, string="Codigo de respuesta del servidor api")

    usar_fact_digi = fields.Boolean(
        related='company_id.usar_fact_digi',
        string="Usar Facturación Digital",
        readonly=True,
        store=True  # Opcional: ver notas abajo
    )

    def print_digital(self):
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




    @api.onchange('journal_id')
    def _compute_proximo_valor(self):
        for rec in self:
            rec.proximo_doc = rec.journal_id.doc_sequence_number_next

    @api.onchange('journal_id')
    def _compute_proximo_ctrl(self):
        for rec in self:
            rec.proximo_ctrl = rec.journal_id.ctrl_sequence_number_next

    

    def confirmar2(self):
        for rec in self:
            if rec.company_id.usar_fact_digi==True:
                rec.valida_pagos_progra_contado()
                #rec.action_post()
                if rec.code!='200':
                    rec.enviar_fact_digital()
                if rec.code=='200':
                    rec.action_post()

    def valida_pagos_progra_contado(self):
        # ELIMINAMOS la restricción que evitaba las Notas de Crédito (refund)
        if self.cond_fact == 'cont': 
            payments_to_process = self.igtf_ids.search([('move_id', '=', self.id)])
            if not payments_to_process:
                # Opcional: Para Notas de Crédito podrías querer que esto no sea obligatorio
                if self.move_type not in ('out_refund', 'in_refund'):
                    raise UserError(_('Debe registrar primero los métodos de pagos para esta factura a contado'))



    def enviar_fact_digital(self):
        """Construye y envía el JSON del documento fiscal hacia Unidigital basándose en la especificación exacta."""
        for move in self:
            company = move.company_id

            # 1. Obtener Token y Serie
            company.unidg_get_token()
            if not company.unidg_jwt_token or not company.seriestrongid:
                raise UserError(_("No se pudo obtener el Token o la Serie de Unidigital."))

            # 2. Tipo de documento y Homologación de Moneda
            doc_type_mapping = {
                'out_invoice': 'FA',
                'out_refund': 'NC',
                'out_receipt': 'ND',
            }
            document_type = doc_type_mapping.get(move.move_type)
            if not document_type:
                raise UserError(_("El tipo de documento '%s' no está soportado.") % move.move_type)

            raw_currency = (move.currency_id.name or '').upper().strip()
            if raw_currency in ('VED', 'VEF', 'BS', 'BS.S', 'VES'):
                currency_code = 'VES'
                conversion_currency_code = 'USD'
            else:
                currency_code = raw_currency
                conversion_currency_code = 'VES'

            # 3. Datos del Cliente / RIF
            partner = move.partner_id
            vat_clean = (partner.vat or '').replace('-', '').strip().upper()
            fiscal_code = vat_clean[0] if vat_clean and vat_clean[0].isalpha() else 'J'
            fiscal_registry = vat_clean[1:] if vat_clean and vat_clean[0].isalpha() else vat_clean

            # 4. Tasa y Fecha
            exchange_rate = getattr(move, 'tasa', 1.0) or 1.0
            emission_date = (move.invoice_date or fields.Date.today()).strftime('%Y-%m-%dT%H:%M:%S.000Z')

            # 5. Filtrar líneas válidas
            lines = move.invoice_line_ids.filtered(lambda l: l.display_type not in ('line_section', 'line_note'))
            if not lines:
                raise UserError(_("La factura no contiene líneas de productos/servicios válidas para enviar."))

            details = []
            tax_base_general = 0.0
            tax_amount_general = 0.0
            tax_base_reduced = 0.0
            tax_amount_reduced = 0.0
            exempt_amount = 0.0

            for line in lines:
                line_tax = line.tax_ids[:1]
                aliquot = line_tax.aliquot if line_tax else False
                tax_rate_amount = line_tax.amount if line_tax else 0.0

                is_exempt = False
                tax_code = "G"
                tax_percent = 16

                line_subtotal = round(line.price_subtotal, 2)
                line_tax_amount = round(line.price_total - line.price_subtotal, 2)
                line_total = round(line.price_total, 2)

                if aliquot == 'exempt' or tax_rate_amount == 0:
                    is_exempt = True
                    tax_code = "E"
                    tax_percent = 0
                    exempt_amount += line_subtotal
                elif aliquot == 'reduced' or tax_rate_amount == 8:
                    tax_code = "R"
                    tax_percent = 8
                    tax_base_reduced += line_subtotal
                    tax_amount_reduced += line_tax_amount
                else:
                    tax_code = "G"
                    tax_percent = 16
                    tax_base_general += line_subtotal
                    tax_amount_general += line_tax_amount

                details.append({
                    "Description": line.name or "Producto/Servicio",
                    "Quantity": line.quantity,
                    "UnitPrice": line.price_unit,
                    "Amount": line_subtotal,
                    "TaxAmount": line_tax_amount,
                    "TaxPercent": tax_percent,
                    "TaxCode": tax_code,
                    "IsExempt": is_exempt,
                    "OperationCode": "C001",
                    "AmountPlusDiscount": line_subtotal,
                    "TotalAmount": line_total,
                    "ProductType": 1
                })

            # Redondeo de totales base del documento
            tax_base_general = round(tax_base_general, 2)
            tax_amount_general = round(tax_amount_general, 2)
            tax_base_reduced = round(tax_base_reduced, 2)
            tax_amount_reduced = round(tax_amount_reduced, 2)
            exempt_amount = round(exempt_amount, 2)

            subtotal_doc = round(tax_base_general + tax_base_reduced + exempt_amount, 2)
            taxes_doc = round(tax_amount_general + tax_amount_reduced, 2)
            total_doc = round(subtotal_doc + taxes_doc, 2)

            # =========================================================================
            # LÓGICA DE CÁLCULO DE IGTF (CONTADO VS CRÉDITO)
            # =========================================================================
            igtf_base_main = 0.0
            igtf_amount_main = 0.0
            payment_type_str = "CONTADO"

            cond_fact = getattr(move, 'cond_fact', 'cont')

            if cond_fact == 'cred':
                payment_type_str = "CREDITO"
                if currency_code == 'USD':
                    igtf_base_main = total_doc
                    igtf_amount_main = round(total_doc * 0.03, 2)
            else:
                payment_type_str = "CONTADO"
                # Buscar pagos en el modelo custom y filtrar en memoria por campo no-stored
                pagos_todos = self.env['account.payment.fact'].search([
                    ('move_id', '=', move.id)
                ])
                pagos_divisa = pagos_todos.filtered(lambda p: (getattr(p, 'porcentage', 0) or 0) > 0)

                if pagos_divisa:
                    if currency_code == 'VES':
                        # Para documento en VES, la base/monto principal del IGTF se envía en VES
                        igtf_base_main = sum(p.monta_a_pagar_bs for p in pagos_divisa)
                        igtf_amount_main = sum(p.monto_ret_bs for p in pagos_divisa)
                    else:
                        igtf_base_main = sum(p.monta_a_pagar for p in pagos_divisa)
                        igtf_amount_main = sum(p.monta_a_pagar * (p.porcentage / 100.0) for p in pagos_divisa)

            igtf_base_main = round(igtf_base_main, 2)
            igtf_amount_main = round(igtf_amount_main, 2)

            grand_total = round(total_doc + igtf_amount_main, 2)

            # =========================================================================
            # CONVERSIÓN A MONEDA SECUNDARIA
            # =========================================================================
            if currency_code == 'VES':
                exempt_conv = round(exempt_amount / exchange_rate, 2) if exchange_rate else 0.0
                tax_base_gen_conv = round(tax_base_general / exchange_rate, 2) if exchange_rate else 0.0
                tax_base_red_conv = round(tax_base_reduced / exchange_rate, 2) if exchange_rate else 0.0
                subtotal_conv = round(subtotal_doc / exchange_rate, 2) if exchange_rate else 0.0
                tax_amount_gen_conv = round(tax_amount_general / exchange_rate, 2) if exchange_rate else 0.0
                tax_amount_red_conv = round(tax_amount_reduced / exchange_rate, 2) if exchange_rate else 0.0
                total_conv = round(total_doc / exchange_rate, 2) if exchange_rate else 0.0

                igtf_base_conv = round(igtf_base_main / exchange_rate, 2) if exchange_rate else 0.0
                igtf_amount_conv = round(igtf_amount_main / exchange_rate, 2) if exchange_rate else 0.0
                grand_total_conv = round(grand_total / exchange_rate, 2) if exchange_rate else 0.0
            else:
                exempt_conv = round(exempt_amount * exchange_rate, 2)
                tax_base_gen_conv = round(tax_base_general * exchange_rate, 2)
                tax_base_red_conv = round(tax_base_reduced * exchange_rate, 2)
                subtotal_conv = round(subtotal_doc * exchange_rate, 2)
                tax_amount_gen_conv = round(tax_amount_general * exchange_rate, 2)
                tax_amount_red_conv = round(tax_amount_reduced * exchange_rate, 2)
                total_conv = round(total_doc * exchange_rate, 2)

                igtf_base_conv = round(igtf_base_main * exchange_rate, 2)
                igtf_amount_conv = round(igtf_amount_main * exchange_rate, 2)
                grand_total_conv = round(grand_total * exchange_rate, 2)

            # 6. Payload Final hacia Unidigital
            payload = {
                "SerieStrongId": company.seriestrongid,
                "SucursalStrongId": company.sucursal_strong_id or "81e836fe-eff1-4ca7-bcfd-5f079a44a503",
                "DocumentType": document_type,
                "Number": int(move.proximo_doc or 0),
                "EmissionDateAndTime": emission_date,
                "Name": partner.name or "Cliente Generico",
                "FiscalRegistryCode": fiscal_code,
                "FiscalRegistry": fiscal_registry,
                "Address": partner.street or "Caracas, Venezuela",
                "Phone": partner.phone or partner.mobile or "02120000000",
                "EmailTo": partner.email or "api@unidigital.global",
                "PaymentType": payment_type_str,
                "Currency": currency_code,
                
                # Subtotales e Impuestos principales
                "ExemptAmount": exempt_amount,
                "TaxBase": tax_base_general,
                "TaxBaseReduced": tax_base_reduced,
                "Subtotal": subtotal_doc,
                "Discount": 0,
                "PreviousBalance": 0,
                "SubtotalPlusDiscount": subtotal_doc,

                "TaxPercent": 16,
                "TaxPercentReduced": 8,
                "TaxPercentSumptuary": 31,
                "TaxAmount": tax_amount_general,
                "TaxAmountReduced": tax_amount_reduced,
                "TaxAmountSumptuary": 0.00,
                "Taxes": taxes_doc,
                "Total": total_doc,

                # IGTF principal
                "IGTFBaseAmount": igtf_base_main,
                "IGTFAmount": igtf_amount_main,
                "IGTFPercentage": 3,
                "GrandTotal": grand_total,
                "AmountLetters": f"{grand_total:.2f} {currency_code}",

                "ConversionCurrency": conversion_currency_code,

                # Conversión / Valores secundarios (USD si la moneda es VES)
                "ExemptAmountVES": exempt_conv,
                "TaxBaseVES": tax_base_gen_conv,
                "TaxBaseReducedVES": tax_base_red_conv,
                "TaxPercentSumptuaryVES": 31,
                "SubtotalVES": subtotal_conv,
                "PreviousBalanceVES": 0,
                "DiscountVES": 0,
                "SubtotalPlusDiscountVES": subtotal_conv,

                "TaxAmountVES": tax_amount_gen_conv,
                "TaxAmountReducedVES": tax_amount_red_conv,
                "TaxAmountSumptuaryVES": 0.00,
                "TotalVES": total_conv,

                # IGTF Convertido
                "IGTFBaseAmountVES": igtf_base_conv,
                "IGTFAmountVES": igtf_amount_conv,
                "GrandTotalVES": grand_total_conv,
                "AmountLettersVES": f"{grand_total_conv:.2f} {conversion_currency_code}",

                "ExchangeRate": exchange_rate,
                "SystemReference": move.name or "",
                "Note1": f"Documento emitido desde Odoo: {move.name}",
                "Note2": "",
                "Note3": "",
                "Extra": {},
                "Details": details
            }

            if document_type in ('NC', 'ND'):
                origin_doc_number = move.fact_afect  #move.reversed_entry_id.proximo_doc or move.ref or "0"
                origin_number_clean = ''.join(filter(str.isdigit, str(origin_doc_number)))
                payload["AffectedDocumentNumber"] = int(origin_number_clean) if origin_number_clean else 0

            # Guardar JSON para auditoría
            move.json_enviado = json.dumps(payload, indent=4, ensure_ascii=False)

            # 7. Envío HTTP
            target_url = move.company_id.url + move.company_id.enpoint_emision
            headers = {
                "Authorization": f"Bearer {company.unidg_jwt_token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }

            try:
                _logger.info("Unidigital: Enviando documento %s a %s", move.name, target_url)
                response = requests.post(target_url, data=json.dumps(payload), headers=headers, timeout=20)
                
                # Guarda el status code HTTP (200, 405, 500, etc.)
                http_status = response.status_code
                res_json = response.json() if response.content else {}

                # Si el JSON trae su propio campo "code", lo usa; de lo contrario toma el código de estado HTTP
                move.code = str(res_json.get("code") if res_json.get("code") is not None else http_status)
                
                move.hasErrors = str(res_json.get("hasErrors", False))
                move.result = json.dumps(res_json.get("result", {}))
                move.information = json.dumps(res_json.get("information", []))

                if http_status in (200, 201) and not res_json.get("hasErrors"):
                    _logger.info("Unidigital: Documento %s procesado con éxito.", move.name)
                    move.errorMessage = ""
                else:
                    errors = res_json.get("errors", [])
                    error_msg = json.dumps(errors) if errors else response.text
                    move.errorMessage = error_msg
                    _logger.error("Unidigital Error al emitir %s: %s", move.name, error_msg)

            except requests.exceptions.RequestException as e:
                move.hasErrors = "True"
                move.code = "500"
                move.errorMessage = f"Error de conexión con la API: {str(e)}"
                _logger.error("Unidigital Excepción de Red: %s", str(e))