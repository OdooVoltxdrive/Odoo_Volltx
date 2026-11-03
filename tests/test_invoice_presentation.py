"""Isolated checks of the production methods; these do not replace Odoo ORM tests."""
import ast
from datetime import date
from decimal import Decimal
from html import escape, unescape
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock


SOURCE = Path(__file__).resolve().parents[1] / 'ext/voltx_fleet_shifts/models/fleet_weekly_liquidation.py'


def load_method(name, source=SOURCE, **globals_):
    tree = ast.parse(source.read_text(encoding='utf-8'))
    method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name)
    namespace = {
        'Command': SimpleNamespace(create=lambda values: (0, 0, values), set=lambda ids: (6, 0, ids)),
        'fields': SimpleNamespace(Date=SimpleNamespace(context_today=lambda record: date(2026, 11, 2))),
        '_': lambda text: text, 'UserError': ValueError, 'escape': escape,
        **globals_,
    }
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), 'exec'), namespace)
    return namespace[name]


class InvoicePresentationTests(unittest.TestCase):
    def setUp(self):
        self.product = SimpleNamespace(id=27, name='Arrendamiento')
        self.template = Mock(product_variant_id=self.product)
        self.template.exists.return_value = self.template
        self.invoice_model = Mock()
        self.invoice_model.with_context.return_value = self.invoice_model
        self.invoice_model.create.return_value = SimpleNamespace(id=48)
        self.vehicle = SimpleNamespace(
            model_id=SimpleNamespace(brand_id=SimpleNamespace(name='TOYOTA')),
            name='TOYOTA / AB123CD', license_plate='AB123CD', vin_sn='1HGCM82633A004352',
        )
        self.company = SimpleNamespace(id=1)
        journal = SimpleNamespace(id=3, default_account_id=SimpleNamespace(id=4))
        env = MagicMock()
        env.company = self.company
        env.__getitem__.side_effect = {
            'account.journal': Mock(search=Mock(return_value=journal)),
            'product.template': Mock(browse=Mock(return_value=self.template)),
            'account.move': self.invoice_model,
        }.__getitem__
        self.record = Mock(
            env=env, invoice_id=False, driver_id=SimpleNamespace(id=2),
            amount_total_usd=97.50, amount_total_bs=0,
            contract_id=SimpleNamespace(company_id=self.company, vehicle_id=self.vehicle),
            currency_id=SimpleNamespace(id=5), fiscal_breakdown=False,
            week_of_year='Semana 45 - 2026', observation='voltx-payment:internal-reference',
        )
        self.record.name = 'voltx-payment:internal-id'
        self.record.with_context.return_value = self.record

    def generate(self):
        load_method('_auto_generate_invoice')(self.record)
        return self.invoice_model.create.call_args.args[0]

    def test_line_contains_only_the_registered_product_name(self):
        values = self.generate()
        self.assertEqual(values['invoice_line_ids'][0][2]['name'], 'Arrendamiento')
        self.assertEqual(values['invoice_line_ids'][0][2]['product_id'], 27)
        self.assertEqual(values['invoice_line_ids'][0][2]['price_unit'], 97.50)
        self.assertEqual(values['state'], 'draft')
        self.assertIn('voltx-payment:internal-id', values['ref'])

    def test_missing_registered_rental_product_does_not_create_an_invoice(self):
        self.template.product_variant_id = False
        with self.assertRaisesRegex(ValueError, 'plantilla 27'):
            self.generate()
        self.invoice_model.create.assert_not_called()

    def test_vehicle_text_is_prepared_in_draft_narration(self):
        self.assertEqual(self.generate()['narration'], 'TOYOTA/AB123CD/1HGCM82633A004352')

    def test_draft_confirmation_sends_prepared_note1_and_only_product_description(self):
        values = self.generate()
        company = Mock(
            unidg_jwt_token='local-test-token', seriestrongid='local-test-series',
            sucursal_strong_id='local-test-branch', usar_fact_digi=True,
            url='https://unidigital.invalid', enpoint_emision='/emit',
        )
        lines = Mock()
        lines.filtered.return_value = [SimpleNamespace(
            name=values['invoice_line_ids'][0][2]['name'], tax_ids=[],
            price_subtotal=97.50, price_total=97.50, price_unit=97.50, quantity=1,
        )]
        invoice = SimpleNamespace(
            company_id=company, currency_id=SimpleNamespace(name='USD'), move_type='out_invoice',
            partner_id=SimpleNamespace(vat='V12345678', name='QA driver', street='QA', phone='0', email='qa@example.invalid'),
            tasa=40, invoice_date=values['invoice_date'], invoice_line_ids=lines, cond_fact='cred',
            narration=values['narration'], proximo_doc=1, name='Draft QA', code=False,
            valida_pagos_progra_contado=Mock(), action_post=Mock(),
        )
        source = SOURCE.parents[3] / 'Facturacion Digital/factura_digital_unidigital/models/account_move.py'
        http = Mock()
        http.post.return_value = Mock(status_code=200, content=b'{}', json=Mock(return_value={'result': 'local-test-id'}))
        send = load_method('enviar_fact_digital', source, json=json, requests=http, _logger=Mock(), html2plaintext=unescape)
        invoice.enviar_fact_digital = lambda: send([invoice])
        load_method('confirmar2', source)([invoice])
        payload = json.loads(http.post.call_args.kwargs['data'])
        self.assertEqual(payload['Note1'], 'TOYOTA/AB123CD/1HGCM82633A004352')
        self.assertEqual(payload['Details'][0]['Description'], 'Arrendamiento')
        self.assertEqual(json.loads(invoice.json_enviado)['Note1'], payload['Note1'])
        invoice.action_post.assert_called_once_with()

    def test_missing_plate_and_vin_do_not_produce_false_or_empty_separators(self):
        self.vehicle.license_plate = False
        self.vehicle.vin_sn = False
        self.assertEqual(self.generate()['narration'], 'TOYOTA')

    def test_narration_escapes_html_without_truncating_vehicle_identifiers(self):
        self.vehicle.model_id.brand_id.name = 'Brand <Fleet> & Co'
        self.assertEqual(
            self.generate()['narration'],
            'Brand &lt;Fleet&gt; &amp; Co/AB123CD/1HGCM82633A004352',
        )

    def test_retry_does_not_recreate_or_rewrite_an_existing_invoice(self):
        self.record.invoice_id = SimpleNamespace(id=48)
        load_method('_auto_generate_invoice')(self.record)
        self.invoice_model.create.assert_not_called()
        self.record.write.assert_not_called()

    def test_fiscal_rental_and_service_lines_use_their_own_product_names(self):
        taxes = MagicMock()
        taxes.filtered.return_value = taxes
        taxes.__len__.return_value = 1
        taxes.amount_type, taxes.amount = 'percent', 16
        taxes.price_include, taxes.include_base_amount = False, False
        taxes.type_tax_use, taxes.ids = 'sale', [6]
        account = SimpleNamespace(id=4, account_type='income')
        products = []
        for name in ('Arrendamiento', 'Servicio registrado'):
            product = Mock(active=True, sale_ok=True, company_id=False, taxes_id=taxes)
            product.name, product.id = name, len(products) + 27
            product.with_company.return_value = SimpleNamespace(property_account_income_id=account)
            products.append(product)
        self.company.voltx_service_product_id = products[1]
        self.record._fiscal_amounts.return_value = {'base': Decimal('3900'), 'service': Decimal('487.50')}
        lines = load_method('_fiscal_invoice_lines')(self.record, self.company, products[0], account)
        self.assertEqual([line[2]['name'] for line in lines], ['Arrendamiento', 'Servicio registrado'])
        self.assertEqual([line[2]['price_unit'] for line in lines], [3900, 487.50])
        self.assertEqual([line[2]['tax_ids'] for line in lines], [[(6, 0, [6])], [(6, 0, [6])]])


if __name__ == '__main__':
    unittest.main()
