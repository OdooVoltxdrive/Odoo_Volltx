from odoo import models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _voltx_usd_fiscal_invoices(self):
        # Read only the links of invoices already accessible to the caller, not fleet-wide data.
        liquidations = self.env['fleet.weekly.liquidation'].sudo().search([
            ('invoice_id', 'in', self._origin.ids),
        ])
        invoices = liquidations.filtered(
            lambda liq: isinstance(liq.fiscal_breakdown, dict)
            and liq.fiscal_breakdown.get('version') == 2
            and liq.fiscal_breakdown.get('currency') == 'USD'
        ).mapped('invoice_id')
        return self.filtered(lambda move: move.id in invoices.ids and move.move_type == 'out_invoice')

    def _voltx_native_tax_amount(self, rate):
        self.ensure_one()
        lines = self.line_ids.filtered(
            lambda line: line.tax_line_id
            and line.tax_line_id.amount_type == 'percent'
            and line.tax_line_id.amount == rate
        )
        return self.currency_id.round(-sum(lines.mapped('amount_currency')))

    def _compute_aliquot_general(self):
        fiscal = self._voltx_usd_fiscal_invoices()
        if self - fiscal:
            super(AccountMove, self - fiscal)._compute_aliquot_general()
        for move in fiscal:
            move.amount_ivag = move._voltx_native_tax_amount(16)

    def _compute_aliquot_reducida(self):
        fiscal = self._voltx_usd_fiscal_invoices()
        if self - fiscal:
            super(AccountMove, self - fiscal)._compute_aliquot_reducida()
        for move in fiscal:
            move.amount_ivar = 0

    def _compute_aliquot_adicional(self):
        fiscal = self._voltx_usd_fiscal_invoices()
        if self - fiscal:
            super(AccountMove, self - fiscal)._compute_aliquot_adicional()
        for move in fiscal:
            move.amount_ivaa = 0

    def _compute_igtf(self):
        fiscal = self._voltx_usd_fiscal_invoices()
        for move in self - fiscal:
            super(AccountMove, move)._compute_igtf()
        for move in fiscal:
            move.amount_igtf = move._voltx_native_tax_amount(3)

    def _compute_total_aux(self):
        fiscal = self._voltx_usd_fiscal_invoices()
        for move in self - fiscal:
            super(AccountMove, move)._compute_total_aux()
        for move in fiscal:
            # Native amount_total already includes the separate IGTF tax line.
            move.amount_total_aux = move.amount_total

    def _check_voltx_usd_draft_only(self):
        if self._voltx_usd_fiscal_invoices():
            raise UserError(_(
                'ODOO_USD_FISCAL_POSTING_MAPPING_REQUIRED: la factura USD con IGTF '
                'permanece en borrador hasta validar el mapeo electrónico Unidigital; '
                'no se debe volver a sumar IGTF al total nativo.'
            ))

    def action_post(self):
        self._check_voltx_usd_draft_only()
        return super().action_post()

    def enviar_fact_digital(self):
        self._check_voltx_usd_draft_only()
        return super().enviar_fact_digital()
