"""CPU tests for active inspection and leakage through observation/feedback/history."""
import json
import unittest
from observation_policy import ObservationPolicy


class ObservationTests(unittest.TestCase):
    def test_requested_hides_changed_state_and_nested_result(self):
        policy = ObservationPolicy('requested', {'fuel': 3}, 0)
        history = [policy.visible(0)]
        for tool in ('fuel','collect_output','store_plates','wait'):
            policy.update({'fuel': 'HIDDEN_LIVE'},900,{'tool':tool},
                          {'transferred':2,'observation':{'fuel':'HIDDEN_LIVE'},'source_before':'HIDDEN_LIVE'},None,
                          [{'iron_plates':'HIDDEN_LIVE'}])
            history.append(policy.visible(900))
        self.assertNotIn('HIDDEN_LIVE',json.dumps(history))
        self.assertEqual(history[-1]['observation_age_ticks'],900)

    def test_successful_check_updates_after_interval(self):
        policy=ObservationPolicy('requested',{'fuel':3},0)
        policy.update({'fuel':2},900,{'tool':'check'},{'fuel':'PRE_ADVANCE'},None,[{'iron_plates':18}])
        visible=policy.visible(900)
        self.assertEqual(visible['observation'],{'fuel':2})
        self.assertEqual(visible['observation_age_ticks'],0)
        self.assertNotIn('PRE_ADVANCE',json.dumps(visible))
        self.assertEqual(policy.inspections,1)

    def test_failed_check_does_not_refresh_or_leak_error(self):
        policy=ObservationPolicy('requested',{'fuel':3},0)
        policy.update({'fuel':'SECRET'},900,{'tool':'check'},{'error':'SECRET'},'RuntimeError SECRET',[])
        self.assertNotIn('SECRET',json.dumps(policy.visible(900)))
        self.assertEqual(policy.inspections,0)

    def test_automatic_updates_with_same_filtered_feedback(self):
        policy=ObservationPolicy('automatic',{'fuel':3},0)
        policy.update({'fuel':2},900,{'tool':'fuel'},{'nested':'PRIVATE'},None,[])
        self.assertEqual(policy.visible(900)['observation'],{'fuel':2})
        self.assertNotIn('PRIVATE',json.dumps(policy.visible(900)))

    def test_private_mutations_cannot_change_retained_or_history_state(self):
        obs={'fuel':[3]}
        policy=ObservationPolicy('requested',obs,0)
        old=policy.visible(0)
        obs['fuel'][0]=99
        old['observation']['fuel'][0]=98
        self.assertEqual(policy.visible(900)['observation'],{'fuel':[3]})

    def test_invalid_tool_text_and_malformed_counts_do_not_leak(self):
        policy=ObservationPolicy('requested',{},0)
        policy.update({},900,{'tool':'SECRET'}, {},'SECRET',[])
        self.assertNotIn('SECRET',json.dumps(policy.visible(900)))
        policy.update({},1800,{'tool':'collect_output'},{'transferred':{'fuel':'SECRET'}},None,[])
        self.assertNotIn('SECRET',json.dumps(policy.visible(1800)))


if __name__=='__main__':
    unittest.main()
