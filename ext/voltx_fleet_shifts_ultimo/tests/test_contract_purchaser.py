from psycopg2 import IntegrityError

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestContractPurchaser(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.driver = cls.env['res.partner'].create({
            'name': 'Contract purchaser QA', 'is_driver': True,
        })
        brand = cls.env['fleet.vehicle.model.brand'].create({'name': 'Purchaser QA'})
        model = cls.env['fleet.vehicle.model'].create({
            'name': 'Purchaser QA', 'brand_id': brand.id,
        })
        cls.vehicle = cls.env['fleet.vehicle'].create({
            'model_id': model.id, 'company_id': cls.env.company.id,
        })

    def _create_contract(self):
        return self.env['fleet.vehicle.log.contract'].create({
            'vehicle_id': self.vehicle.id,
            'purchaser_id': self.driver.id,
        })

    def _legacy_contract(self):
        contract = self._create_contract()
        self.env.flush_all()
        # Reproduce los datos heredados sin pasar por las validaciones de altas nuevas.
        self.env.cr.execute(
            'UPDATE fleet_vehicle_log_contract SET purchaser_id = NULL WHERE id = %s',
            [contract.id],
        )
        contract.invalidate_recordset(['purchaser_id'])
        return contract

    def test_legacy_schema_does_not_require_inventing_purchasers(self):
        self.env.cr.execute("""
            SELECT is_nullable FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'fleet_vehicle_log_contract'
              AND column_name = 'purchaser_id'
        """)
        self.assertEqual(self.env.cr.fetchone()[0], 'YES')

    def test_form_keeps_purchaser_required(self):
        arch = self.env.ref('fleet.fleet_vehicle_log_contract_view_form')._get_combined_arch()
        fields = arch.xpath("//field[@name='purchaser_id']")
        self.assertTrue(fields)
        self.assertTrue(all(field.get('required') == '1' for field in fields))

    def test_new_contract_requires_purchaser(self):
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env['fleet.vehicle.log.contract'].create({
                'vehicle_id': self.vehicle.id,
            })

    def test_valid_contract_keeps_explicit_purchaser(self):
        self.assertEqual(self._create_contract().purchaser_id, self.driver)

    def test_context_default_purchaser_remains_supported(self):
        contract = self.env['fleet.vehicle.log.contract'].with_context(
            default_purchaser_id=self.driver.id,
        ).create({'vehicle_id': self.vehicle.id})
        self.assertEqual(contract.purchaser_id, self.driver)

    def test_vehicle_driver_fallback_remains_supported(self):
        self.vehicle.driver_id = self.driver
        contract = self.env['fleet.vehicle.log.contract'].create({
            'vehicle_id': self.vehicle.id,
        })
        self.assertEqual(contract.purchaser_id, self.driver)

    def test_purchaser_cannot_be_cleared(self):
        contract = self._create_contract()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            contract.write({'purchaser_id': False})
        self.assertEqual(contract.purchaser_id, self.driver)

    def test_linked_purchaser_cannot_be_deleted(self):
        self._create_contract()
        self.env.cr.execute("""
            SELECT c.confdeltype FROM pg_constraint c
            JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
            WHERE c.contype = 'f'
              AND c.conrelid = 'fleet_vehicle_log_contract'::regclass
              AND a.attname = 'purchaser_id'
        """)
        self.assertEqual(self.env.cr.fetchone()[0], 'r')
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError), self.env.cr.savepoint():
            self.driver.unlink()

    def test_contract_owner_does_not_change_vehicle_current_driver(self):
        other_driver = self.env['res.partner'].create({
            'name': 'Different current driver QA', 'is_driver': True,
        })
        self.vehicle.driver_id = other_driver
        contract = self._create_contract()
        self.assertEqual(contract.purchaser_id, self.driver)
        self.assertEqual(self.vehicle.driver_id, other_driver)

    def test_current_driver_changes_do_not_remove_contract_owner(self):
        contract = self._create_contract()
        self.vehicle.write({'driver_id': self.driver.id})
        self.vehicle.write({'driver_id': False})
        self.assertFalse(self.vehicle.driver_id)
        self.assertEqual(contract.purchaser_id, self.driver)

    def test_turn_sync_does_not_clear_contract_owner(self):
        contract = self._create_contract()
        contract.with_context(sync_vehicle_turn=True).write({'purchaser_id': False})
        self.assertEqual(contract.purchaser_id, self.driver)

    def test_legacy_contract_can_be_preserved_and_repaired(self):
        contract = self._legacy_contract()
        contract.write({'start_time': '06:00'})
        self.assertFalse(contract.purchaser_id)
        self.assertEqual(contract.start_time, '06:00')
        contract.write({'purchaser_id': self.driver.id})
        self.assertEqual(contract.purchaser_id, self.driver)

    def test_legacy_contract_without_driver_cannot_generate_invoice(self):
        contract = self._legacy_contract()
        liquidation = self.env['fleet.weekly.liquidation'].create({
            'contract_id': contract.id,
            'week_of_year': 'Semana 43 - 2026',
            'amount_total_usd': 97.50,
        })
        self.assertFalse(liquidation.invoice_id)
        with self.assertRaises(UserError):
            liquidation.action_generate_invoice()

    def test_invalid_batch_does_not_leave_partial_contracts(self):
        contracts = self.env['fleet.vehicle.log.contract']
        unassigned_vehicle = self.env['fleet.vehicle'].create({
            'model_id': self.vehicle.model_id.id, 'company_id': self.env.company.id,
        })
        before = contracts.search_count([])
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            contracts.create([
                {'vehicle_id': self.vehicle.id, 'purchaser_id': self.driver.id},
                {'vehicle_id': unassigned_vehicle.id},
            ])
        self.assertEqual(contracts.search_count([]), before)

    def test_driver_assignment_keeps_one_contract_and_history(self):
        self.vehicle.write({'driver_ids': [Command.link(self.driver.id)]})
        self.vehicle.write({'driver_ids': [Command.link(self.driver.id)]})
        contracts = self.env['fleet.vehicle.log.contract'].search([
            ('vehicle_id', '=', self.vehicle.id),
            ('purchaser_id', '=', self.driver.id),
            ('state', 'in', ['open', 'futur']),
        ])
        self.assertEqual(len(contracts), 1)
        self.assertEqual(self.env['fleet.vehicle.driver.history'].search_count([
            ('vehicle_id', '=', self.vehicle.id),
            ('driver_id', '=', self.driver.id),
            ('date_end', '=', False),
        ]), 1)
