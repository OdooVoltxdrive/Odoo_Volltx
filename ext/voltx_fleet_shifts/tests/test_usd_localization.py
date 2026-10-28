from odoo.exceptions import UserError
from odoo.tests import tagged

from .test_liquidation_fiscal import TestLiquidationFiscalUsd


@tagged('post_install', '-at_install')
class TestUsdFiscalLocalization(TestLiquidationFiscalUsd):
    def setUp(self):
        super().setUp()
        # Reproduce the real localization configuration: both copies are general.
        (self.usd_vat | self.igtf).aliquot = 'general'
        self.tax_sale_a.aliquot = 'general'

    def test_read_fiscal_form_fields_uses_native_vat_and_igtf_once(self):
        move = self._create_usd().invoice_id
        [values] = move.read(['amount_ivag', 'amount_ivar', 'amount_ivaa', 'amount_igtf', 'amount_total_aux'])
        self.assertEqual(values['amount_ivag'], 15.60)
        self.assertEqual(values['amount_ivar'], 0)
        self.assertEqual(values['amount_ivaa'], 0)
        self.assertEqual(values['amount_igtf'], 3.39)
        self.assertEqual(values['amount_total_aux'], 116.49)
        self._assert_draft(self.env['fleet.weekly.liquidation'].search([('invoice_id', '=', move.id)]), self.usd, 116.49)

    def test_reads_do_not_depend_on_current_company_tax_configuration(self):
        move = self._create_usd().invoice_id
        self.env.company.write({'voltx_usd_vat_tax_id': False, 'voltx_igtf_tax_id': False})
        [values] = move.read(['amount_ivag', 'amount_igtf', 'amount_total_aux'])
        self.assertEqual(values['amount_ivag'], 15.60)
        self.assertEqual(values['amount_igtf'], 3.39)
        self.assertEqual(values['amount_total_aux'], 116.49)

    def test_mixed_batch_preserves_ves_localization(self):
        usd = self._create_usd().invoice_id
        ves = self._create_fiscal().invoice_id
        values = {value['id']: value for value in (usd | ves).read(['amount_ivag', 'amount_igtf', 'amount_total_aux'])}
        self.assertEqual(values[usd.id]['amount_ivag'], 15.60)
        self.assertEqual(values[usd.id]['amount_total_aux'], 116.49)
        self.assertEqual(values[ves.id]['amount_ivag'], 702)
        self.assertEqual(values[ves.id]['amount_igtf'], 0)
        self.assertEqual(values[ves.id]['amount_total_aux'], 5089.50)

    def test_posting_requires_separate_electronic_fiscal_mapping(self):
        move = self._create_usd().invoice_id
        for action in (move.action_post, move.enviar_fact_digital):
            with self.subTest(action=action.__name__), self.assertRaisesRegex(UserError, 'ODOO_USD_FISCAL_POSTING_MAPPING_REQUIRED'):
                action()
        self.assertEqual(move.state, 'draft')
