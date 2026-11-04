from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestLiquidationCurrency(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(su=True)
        cls.usd = cls.env.ref('base.USD')
        cls.ves = cls.env.ref('base.VES')
        (cls.usd | cls.ves).active = True
        cls.env.company.currency_id = cls.ves
        cls.company_data['default_journal_sale'].write({
            'currency_id': False,
            'default_account_id': cls.company_data['default_account_revenue'].id,
        })
        cls.product_a.taxes_id = [Command.clear()]
        brand = cls.env['fleet.vehicle.model.brand'].create({'name': 'Currency QA'})
        model = cls.env['fleet.vehicle.model'].create({
            'name': 'Currency QA', 'brand_id': brand.id,
        })
        vehicle = cls.env['fleet.vehicle'].create({
            'model_id': model.id, 'company_id': cls.env.company.id,
        })
        cls.contract = cls.env['fleet.vehicle.log.contract'].create({
            'vehicle_id': vehicle.id,
            'purchaser_id': cls.partner_a.id,
            'company_id': cls.env.company.id,
        })

    def setUp(self):
        super().setUp()
        product_model = type(self.env['product.template'])
        original_browse = product_model.browse
        product_id = self.product_a.product_tmpl_id.id
        # El catálogo 27 es propio del despliegue; solo sustituimos su búsqueda en la prueba.
        self.patch(product_model, 'browse', lambda model, ids=(): original_browse(
            model, product_id if ids == 27 else ids,
        ))

    def _create_liquidation(self, **values):
        return self.env['fleet.weekly.liquidation'].create({
            'contract_id': self.contract.id,
            'week_of_year': 'Semana 43 - 2026',
            **values,
        })

    def _assert_draft(self, liquidation, currency, amount):
        invoice = liquidation.invoice_id
        self.assertTrue(invoice)
        self.assertEqual(invoice.move_type, 'out_invoice')
        self.assertEqual(invoice.state, 'draft')
        self.assertEqual(invoice.auto_post, 'no')
        self.assertEqual(invoice.payment_state, 'not_paid')
        self.assertEqual(invoice.company_id, self.contract.company_id)
        self.assertEqual(invoice.partner_id, self.partner_a)
        self.assertEqual(invoice.currency_id, currency)
        self.assertAlmostEqual(invoice.amount_total, amount, places=2)
        self.assertNotEqual(liquidation.state, 'paid')
        return invoice

    def test_monetary_fields_have_distinct_usd_and_ves_currencies(self):
        liquidation = self._create_liquidation()
        fields = liquidation.fields_get(
            ['amount_total_usd', 'amount_total_bs'], attributes=['currency_field'],
        )
        self.assertEqual(fields['amount_total_usd']['currency_field'], 'currency_id')
        self.assertEqual(fields['amount_total_bs']['currency_field'], 'bs_currency_id')
        self.assertEqual(liquidation.currency_id, self.usd)
        self.assertEqual(liquidation.bs_currency_id, self.ves)
        self.env.company.currency_id = self.usd
        self.assertEqual(liquidation.bs_currency_id, self.ves)

    def test_usd_create_ignores_conflicting_default_currency(self):
        self.env = self.env(context={**self.env.context, 'default_currency_id': self.ves.id})
        liquidation = self._create_liquidation(amount_total_usd=97.50)
        self._assert_draft(liquidation, self.usd, 97.50)

    def test_ves_create_ignores_conflicting_default_currency(self):
        self.env = self.env(context={**self.env.context, 'default_currency_id': self.usd.id})
        liquidation = self._create_liquidation(amount_total_bs=3900)
        self._assert_draft(liquidation, self.ves, 3900)

    def test_ves_invoice_does_not_follow_company_usd_currency(self):
        self.env.company.currency_id = self.usd
        liquidation = self._create_liquidation(amount_total_bs=3900)
        self._assert_draft(liquidation, self.ves, 3900)

    def test_inherited_skip_context_keeps_native_invoice_calculations(self):
        self.env = self.env(context={**self.env.context, 'skip_invoice_sync': True})
        liquidation = self._create_liquidation(amount_total_usd=97.50)
        self._assert_draft(liquidation, self.usd, 97.50)

    def test_write_amount_creates_usd_draft(self):
        liquidation = self._create_liquidation()
        self.assertFalse(liquidation.invoice_id)
        liquidation.write({'amount_total_usd': 97.50})
        self._assert_draft(liquidation, self.usd, 97.50)

    def test_manual_button_creates_ves_draft(self):
        liquidation = self._create_liquidation()
        liquidation.with_context(skip_invoice_sync=True).write({'amount_total_bs': 3900})
        self.assertFalse(liquidation.invoice_id)
        action = liquidation.action_generate_invoice()
        invoice = self._assert_draft(liquidation, self.ves, 3900)
        self.assertEqual(action['res_id'], invoice.id)

    def test_both_amounts_preserve_existing_usd_precedence(self):
        liquidation = self._create_liquidation(amount_total_usd=97.50, amount_total_bs=3900)
        self._assert_draft(liquidation, self.usd, 97.50)

    def test_repeated_generation_does_not_duplicate_or_change_invoice(self):
        liquidation = self._create_liquidation(amount_total_usd=97.50)
        invoice = liquidation.invoice_id
        before = self.env['account.move'].search_count([])
        liquidation._auto_generate_invoice()
        liquidation.write({'amount_total_bs': 3900})
        self.assertEqual(liquidation.invoice_id, invoice)
        self.assertEqual(self.env['account.move'].search_count([]), before)
        self._assert_draft(liquidation, self.usd, 97.50)
        with self.assertRaises(UserError):
            liquidation.action_generate_invoice()

    def test_zero_amount_does_not_create_invoice(self):
        liquidation = self._create_liquidation()
        self.assertFalse(liquidation.invoice_id)
        with self.assertRaises(UserError):
            liquidation.action_generate_invoice()

    def test_product_taxes_are_not_removed_by_currency_patch(self):
        self.tax_sale_a.amount = 16
        self.product_a.taxes_id = [Command.set(self.tax_sale_a.ids)]
        liquidation = self._create_liquidation(amount_total_usd=97.50)
        self._assert_draft(liquidation, self.usd, 113.10)
        self.assertAlmostEqual(liquidation.invoice_id.amount_tax, 15.60, places=2)
