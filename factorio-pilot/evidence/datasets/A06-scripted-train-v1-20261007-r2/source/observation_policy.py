"""Explicit agent-visible observations, separate from private evaluator state."""
from copy import deepcopy


class ObservationPolicy:
    """Refresh on every action or only on successful checks; retain real timestamps."""
    def __init__(self, mode, observation, tick):
        if mode not in ('automatic', 'requested'):
            raise ValueError('Unknown observation policy')
        self.mode = mode
        self.snapshot = deepcopy(observation)
        self.observed_tick = tick
        self.windows = []
        self.inspections = 0
        self.feedback = None

    def update(self, observation, tick, action, result, error, windows):
        """Never pass nested raw results or exception text into model feedback."""
        tool = action.get('tool') if isinstance(action, dict) else None
        ok = error is None
        checked = ok and tool == 'check'
        self.inspections += int(checked)
        self.feedback = {'ok': ok, 'tool': tool if tool in ('fuel','collect_output','store_plates','check','wait') else 'invalid'}
        if not ok:
            self.feedback['error'] = 'Action failed; inspect if current factory state is needed. Check the tool arguments.'
        elif tool in ('collect_output','store_plates'):
            count = result.get('transferred') if isinstance(result, dict) else None
            if type(count) is int and 0 <= count <= 100:
                self.feedback['transferred_iron_plates'] = count
        if self.mode == 'automatic' or checked:
            self.snapshot = deepcopy(observation)
            self.observed_tick = tick
            self.windows = deepcopy(windows[-2:])

    def visible(self, tick):
        """Return an independent prompt payload with stale-state age explicitly disclosed."""
        if tick < self.observed_tick:
            raise ValueError('Observation time is ahead of the decision')
        return deepcopy({'observation_policy': self.mode, 'observation': self.snapshot,
                         'observation_tick': self.observed_tick, 'elapsed_ticks': tick,
                         'observation_age_ticks': tick-self.observed_tick,
                         'result': self.feedback, 'recent_production_windows': self.windows})
