"""Bounded memory of observed facts; no model calls or hidden game queries."""
from collections import deque
import json

class ContextMemory:
    def __init__(self):
        self.entities = {}
        self.failures = deque(maxlen=4)

    def update(self, observation, action=None, error=None, valid_handles=None):
        if valid_handles is not None:
            self.entities = {h: v for h, v in self.entities.items() if h in valid_handles}
        tick = observation['game_tick']
        for entity in observation['entities']:
            if isinstance(entity, dict) and 'handle' in entity:
                fields = {k: entity[k] for k in ('handle','name','position','direction','status','fuel','fuel_inventory','drop_position','warnings') if k in entity}
                self.entities[entity['handle']] = {'observed_tick': tick, **fields}
        if error is not None:
            self.failures.append({'observed_tick': tick, 'action': action, 'error': error[:240]})

    def render(self, tokenizer, max_tokens=512):
        # Keep newest complete records. Never truncate JSON or invent summaries.
        data = {'facts_are_last_observed_not_guaranteed_current': True,
                'recent_failures': list(self.failures),
                'equipment': sorted(self.entities.values(), key=lambda e: e['observed_tick'], reverse=True)}
        while True:
            text = json.dumps(data, separators=(',', ':'))
            count = len(tokenizer.encode(text, add_special_tokens=False))
            if count <= max_tokens:
                return text, count
            if data['equipment']:
                data['equipment'].pop()
            elif data['recent_failures']:
                data['recent_failures'].pop(0)
            else:
                raise RuntimeError('Memory header exceeds token budget')
