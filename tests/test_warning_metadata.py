import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class WarningMetadataTests(unittest.TestCase):
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
