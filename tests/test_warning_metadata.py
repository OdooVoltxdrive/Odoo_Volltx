import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LOCALIZATION = ROOT / 'Localizacion_contable'


class WarningMetadataTests(unittest.TestCase):
    def test_retention_manifests_declare_existing_default_license(self):
        for addon in ('iva_retention', 'isrl_retention'):
            with self.subTest(addon=addon):
                manifest = ast.literal_eval((LOCALIZATION / addon / '__manifest__.py').read_text(encoding='utf-8'))
                self.assertEqual(manifest.get('license'), 'LGPL-3')

    def test_report_fields_use_supported_parameters(self):
        path = LOCALIZATION / 'isrl_retention/wizards/wizard_xml.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword):
                self.assertNotEqual(node.arg, 'filters')

    def test_readonly_declarations_are_booleans(self):
        for relative in ('iva_retention/models/account_move.py', 'isrl_retention/wizards/wizard_xml.py'):
            tree = ast.parse((LOCALIZATION / relative).read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node, ast.keyword) and node.arg == 'readonly':
                    with self.subTest(file=relative, line=node.lineno):
                        self.assertIsInstance(node.value, ast.Constant)
                        self.assertIs(type(node.value.value), bool)

    def test_retention_models_have_explicit_descriptions(self):
        expected = {
            'iva_retention/models/retention_vat.py': ('vat.retention', 'vat.retention.invoice.line'),
            'isrl_retention/models/retention_vat.py': ('isrl.retention', 'isrl.retention.invoice.line'),
            'isrl_retention/models/islr_concept.py': ('islr.concept',),
            'isrl_retention/wizards/wizard_xml.py': ('account.xml.wizard', 'account.xml.wizard.descargar'),
            'isrl_retention/wizards/wizard_arc.py': ('account.arc.wizard',),
        }
        for relative, names in expected.items():
            tree = ast.parse((LOCALIZATION / relative).read_text(encoding='utf-8'))
            descriptions = {}
            for cls in (node for node in tree.body if isinstance(node, ast.ClassDef)):
                values = {
                    target.id: statement.value.value
                    for statement in cls.body if isinstance(statement, ast.Assign)
                    for target in statement.targets if isinstance(target, ast.Name)
                    if isinstance(statement.value, ast.Constant)
                }
                descriptions[values.get('_name')] = values.get('_description')
            for name in names:
                with self.subTest(model=name):
                    self.assertTrue(descriptions.get(name))

    def test_liquidation_does_not_declare_unsupported_tracking(self):
        path = ROOT / 'ext/voltx_fleet_shifts/models/fleet_weekly_liquidation.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id in ('amount_total_usd', 'amount_total_bs')
                for target in node.targets
            ):
                self.assertIsInstance(node.value, ast.Call)
                self.assertNotIn('tracking', [keyword.arg for keyword in node.value.keywords])


if __name__ == '__main__':
    unittest.main()
