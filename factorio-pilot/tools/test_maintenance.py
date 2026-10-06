import unittest
from unittest.mock import patch
from types import SimpleNamespace
from maintenance_tools import MaintenanceBridge, ProductionMonitor
from logistics_tools import LogisticsBridge


class MaintenanceTests(unittest.TestCase):
    def test_target_does_not_terminate_and_streak_resets(self):
        monitor = ProductionMonitor(0, 0)
        plates = 0
        for index, count in enumerate([19, 0, 19, 15, 0], 1):
            plates += count
            monitor.sample(index*3600, plates)
            self.assertEqual(monitor.failed, index == 5)
        self.assertEqual(monitor.windows[2]['consecutive_low_windows'], 0)

    def test_partial_window_and_bad_clock(self):
        monitor = ProductionMonitor(100, 5)
        self.assertIsNone(monitor.sample(1000, 9))
        with self.assertRaises(RuntimeError):
            monitor.sample(3701, 24)
        with self.assertRaises(RuntimeError):
            monitor.sample(3700, 4)

    def test_finish_and_oversized_refills_rejected(self):
        bridge = MaintenanceBridge(SimpleNamespace(namespace=SimpleNamespace(agent_index=0)))
        for action in [{'tool': 'finish', 'args': {}}, {'tool': 'fuel', 'args': {'building_handle': 'e1', 'coal_count': 50}}]:
            with self.assertRaises(ValueError):
                bridge.action(action)

    def test_idle_does_not_advance_simulation_itself(self):
        bridge = MaintenanceBridge(SimpleNamespace(namespace=SimpleNamespace(agent_index=0)))
        with patch.object(bridge, 'advance', side_effect=AssertionError('No double advancement')):
            self.assertTrue(bridge.action({'tool': 'wait', 'args': {}})['idle'])
        with self.assertRaises(ValueError):
            bridge.action({'tool': 'wait', 'args': {'seconds': 60}})

    def test_valid_fueling_uses_existing_adapter(self):
        bridge = MaintenanceBridge(SimpleNamespace(namespace=SimpleNamespace(agent_index=0)))
        action = {'tool': 'fuel', 'args': {'building_handle': 'e1', 'coal_count': 3}}
        with patch.object(LogisticsBridge, 'action', return_value={'inserted': 3}) as call:
            self.assertEqual(bridge.action(action)['inserted'], 3)
            call.assert_called_once_with(action)


if __name__ == '__main__':
    unittest.main()
