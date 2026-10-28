"""Run through `odoo shell` on the disposable voltx_fiscal_test database only."""
import json
import os
from odoo import Command
from odoo.exceptions import UserError

assert env.cr.dbname == 'voltx_fiscal_test'
assert os.environ.get('FISCAL_QA_PASSWORD'), 'Set a local-only QA password'
assert not env['fleet.weekly.liquidation'].search_count([]), 'Never overwrite an existing fixture'
company = env.company
company.country_id = env.ref('base.us')
env['account.chart.template'].try_loading('generic_coa', company=company, install_demo=False)
usd, ves = env.ref('base.USD'), env.ref('base.VES')
(usd | ves).active = True
company.currency_id = ves
revenue = env['account.account'].with_company(company).search([
    *env['account.account']._check_company_domain(company), ('account_type', '=', 'income'),
], limit=1)
journal = env['account.journal'].search([('type', '=', 'sale'), ('company_id', '=', company.id)], limit=1)
journal.write({'currency_id': False, 'default_account_id': revenue.id})
group = env['account.tax.group'].create({'name': 'IVA 16% QA', 'country_id': company.country_id.id})
tax = env['account.tax'].create({'name': 'QA IVA 16%', 'amount': 16, 'amount_type': 'percent',
                                'type_tax_use': 'sale', 'company_id': company.id, 'tax_group_id': group.id})
# The deployed addon uses template 27; reproduce that catalog ID only in this empty local fixture.
assert not env['product.template'].browse(27).exists()
env.cr.execute('SELECT last_value FROM product_template_id_seq')
previous = env.cr.fetchone()[0]
env.cr.execute("SELECT setval('product_template_id_seq', 26)")
rental = env['product.template'].create({'name': 'QA Arrendamiento fiscal', 'type': 'service',
    'taxes_id': [Command.set(tax.ids)], 'property_account_income_id': revenue.id})
assert rental.id == 27
env.cr.execute("SELECT setval('product_template_id_seq', %s)", [max(previous, 27)])
service = env['product.template'].create({'name': 'QA Servicio fiscal confirmado', 'type': 'service',
    'taxes_id': [Command.set(tax.ids)], 'property_account_income_id': revenue.id})
partner = env['res.partner'].create({'name': 'QA Fiscal Local — Solo pruebas', 'is_driver': True})
brand = env['fleet.vehicle.model.brand'].create({'name': 'Fiscal QA'})
model = env['fleet.vehicle.model'].create({'name': 'Fiscal QA', 'brand_id': brand.id})
vehicle = env['fleet.vehicle'].create({'model_id': model.id, 'license_plate': 'LOCAL-FISCAL-QA'})
contract = env['fleet.vehicle.log.contract'].create({'vehicle_id': vehicle.id, 'purchaser_id': partner.id, 'company_id': company.id})
values = {'contract_id': contract.id, 'week_of_year': 'Semana 44 - 2026', 'name': 'QA-FISCAL-VES', 'amount_total_bs': 5089.50,
          'fiscal_breakdown': {'version': 1, 'currency': 'VES', 'base': '3900.00', 'service': '487.50', 'vat': '702.00', 'total': '5089.50'}}
try:
    with env.cr.savepoint():
        env['fleet.weekly.liquidation'].create(values)
except UserError as error:
    assert 'ODOO_LIQUIDATION_SERVICE_MAPPING_REQUIRED' in str(error)
else:
    raise AssertionError('Missing accounting mapping was accepted')
assert not env['fleet.weekly.liquidation'].search_count([])
company.voltx_service_product_id = service.product_variant_id
liquidation = env['fleet.weekly.liquidation'].create(values)
invoice = liquidation.invoice_id
assert invoice.state == 'draft' and invoice.payment_state == 'not_paid' and invoice.auto_post == 'no'
assert ves.compare_amounts(invoice.amount_total, 5089.50) == 0
assert ves.compare_amounts(invoice.amount_tax, 702) == 0
env.ref('base.user_admin').write({'login': 'fiscal-qa', 'password': os.environ['FISCAL_QA_PASSWORD']})
fixture = {'database': env.cr.dbname, 'invoiceId': invoice.id,
           'invoiceActionId': env.ref('account.action_move_out_invoice_type').id, 'companyId': company.id,
           'companyActionId': env['ir.actions.act_window'].search([('res_model', '=', 'res.company')], limit=1).id}
with open('/tmp/fiscal-ui-fixture.json', 'w') as output:
    json.dump(fixture, output)
env.cr.commit()
print('LOCAL_FISCAL_FIXTURE_READY', json.dumps(fixture))
