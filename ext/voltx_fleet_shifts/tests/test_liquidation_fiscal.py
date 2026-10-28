from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from .test_liquidation_currency import TestLiquidationCurrency


@tagged('post_install', '-at_install')
class TestLiquidationFiscal(TestLiquidationCurrency):
    def setUp(self):
        super().setUp()
        self.tax_sale_a.amount = 16
        self.product_a.taxes_id = [Command.set(self.tax_sale_a.ids)]
        self.product_b.taxes_id = [Command.set(self.tax_sale_a.ids)]
        self.product_b.property_account_income_id = self.company_data['default_account_revenue']
        self.env.company.voltx_service_product_id = self.product_b

    def _fiscal(self, **changes):
        return {'version': 1, 'currency': 'VES', 'base': '3900.00', 'service': '487.50',
                'vat': '702.00', 'total': '5089.50', **changes}

    def _create_fiscal(self, **changes):
        return self._create_liquidation(amount_total_bs=5089.50, fiscal_breakdown=self._fiscal(**changes))

    def test_fiscal_ves_two_lines_native_vat_exact_total(self):
        liq = self._create_fiscal()
        move = self._assert_draft(liq, self.ves, 5089.50)
        self.assertEqual(len(move.invoice_line_ids), 2)
        self.assertAlmostEqual(move.amount_untaxed, 4387.50, places=2)
        self.assertAlmostEqual(move.amount_tax, 702, places=2)
        self.assertEqual(move.invoice_line_ids.mapped('product_id'), self.product_a | self.product_b)
        self.assertAlmostEqual(move.invoice_line_ids[0].price_unit, 3900, places=2)
        self.assertAlmostEqual(move.invoice_line_ids[1].price_unit, 487.50, places=2)

    def test_missing_accounting_mapping_rolls_back(self):
        self.env.company.voltx_service_product_id = False
        before = self.env['account.move'].search_count([])
        with self.assertRaisesRegex(UserError, 'ODOO_LIQUIDATION_SERVICE_MAPPING_REQUIRED'), self.cr.savepoint():
            self._create_fiscal()
        self.assertEqual(self.env['account.move'].search_count([]), before)

    def test_wrong_product_tax_rolls_back(self):
        self.product_b.taxes_id = [Command.clear()]
        with self.assertRaisesRegex(UserError, 'ODOO_LIQUIDATION_TAX_MAPPING_REQUIRED'), self.cr.savepoint():
            self._create_fiscal()

    def test_bad_snapshot_is_rejected(self):
        for changes in ({'vat': '701.00'}, {'base': '-1'}, {'currency': 'USD'}, {'version': 2}, {'vat': 'NaN'}):
            with self.subTest(changes=changes), self.assertRaises(UserError), self.cr.savepoint():
                self._create_fiscal(**changes)

    def test_mapped_financial_fields_cannot_change_after_invoicing(self):
        liq = self._create_fiscal()
        for changes in ({'fiscal_breakdown': self._fiscal(base='1')}, {'amount_total_bs': 5000}, {'contract_id': False}):
            with self.subTest(changes=changes), self.assertRaises(UserError), self.cr.savepoint():
                liq.write(changes)
        self._assert_draft(liq, self.ves, 5089.50)

    def test_zero_service_needs_no_service_product(self):
        self.env.company.voltx_service_product_id = False
        liq = self._create_liquidation(amount_total_bs=4524, fiscal_breakdown=self._fiscal(service='0.00', vat='624.00', total='4524.00'))
        self.assertEqual(len(liq.invoice_id.invoice_line_ids), 1)
        self._assert_draft(liq, self.ves, 4524)

    def test_wrong_expected_total_does_not_leave_invoice(self):
        before = self.env['account.move'].search_count([])
        with self.assertRaises(UserError), self.cr.savepoint():
            self._create_fiscal(total='5089.49')
        self.assertEqual(self.env['account.move'].search_count([]), before)

    def test_native_rounding_mismatch_does_not_leave_draft(self):
        self.env.company.tax_calculation_rounding_method = 'round_per_line'
        before = self.env['account.move'].search_count([])
        with self.assertRaisesRegex(UserError, 'cálculos nativos'), self.cr.savepoint():
            self._create_liquidation(amount_total_bs=2.39, fiscal_breakdown=self._fiscal(base='1.03', service='1.03', vat='0.33', total='2.39'))
        self.assertEqual(self.env['account.move'].search_count([]), before)

    def test_service_requires_confirmed_income_account(self):
        self.product_b.property_account_income_id = False
        self.product_b.categ_id.property_account_income_categ_id = False
        with self.assertRaisesRegex(UserError, 'cuenta de ingresos'), self.cr.savepoint():
            self._create_fiscal()

    def test_retry_preserves_same_draft(self):
        liq = self._create_fiscal()
        invoice = liq.invoice_id
        liq._auto_generate_invoice()
        self.assertEqual(liq.invoice_id, invoice)
        self._assert_draft(liq, self.ves, 5089.50)
