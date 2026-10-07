"""CPU safeguards for matched evaluation and workflow identity."""
import json
import tempfile
import unittest
from pathlib import Path
from a06_episode import relative_windows, maintenance_opportunity


class ExecutionTests(unittest.TestCase):
    def test_monitor_origin_not_exposed(self):
        windows = [{'start_tick':10000,'end_tick':13600,'actual_ticks':3600,'iron_plates':18}]
        projected = relative_windows(windows,10000)
        self.assertEqual(projected[0]['start_tick'],0)
        self.assertEqual(projected[0]['end_tick'],3600)
        self.assertEqual(windows[0]['start_tick'],10000)

    def test_wait_heuristic_distinguishes_idle_from_maintenance(self):
        def obs(coal=2,carried=0,output=30):
            return {'carrying':{'carried_plates':carried},'equipment':[
                {'name':'burner-mining-drill','burner':{'coal_in_fuel_inventory':coal}},
                {'name':'stone-furnace','burner':{'coal_in_fuel_inventory':2},'output_storage':{'iron_plates':output}},
                {'name':'wooden-chest','output_storage':{'iron_plates':0}}]}
        self.assertFalse(maintenance_opportunity(obs()))
        self.assertTrue(maintenance_opportunity(obs(coal=1)))
        self.assertTrue(maintenance_opportunity(obs(carried=1)))
        self.assertTrue(maintenance_opportunity(obs(output=60)))

    def test_no_held_out_correction_partition(self):
        root = Path(__file__).resolve().parents[2]
        plan = json.loads((root/'factorio-pilot/protocols/a06-two-round-v1.json').read_text())
        self.assertIn('train fixtures only',plan['round2']['correction_source'])
        self.assertIn('before any final test',plan['final_evaluation']['test_opening_gate'])
        self.assertFalse(plan['training']['custom_rmsnorm'])


if __name__ == '__main__':
    unittest.main()
