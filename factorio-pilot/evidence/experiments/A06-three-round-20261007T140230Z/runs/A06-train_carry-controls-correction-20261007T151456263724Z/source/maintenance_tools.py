"""Maintenance-only interface: every decision consumes a fixed simulation interval."""
from logistics_tools import LogisticsBridge


class MaintenanceBridge(LogisticsBridge):
    SPECS = {
        'fuel': (('building_handle', 'coal_count'), ('building_handle', 'coal_count'),
                 'Refill an observed drill or furnace from carried coal. Integer coal_count 1..3. BOTH machines consume fuel. This refill limit is a benchmark rule.'),
        'collect_output': LogisticsBridge.SPECS['collect_output'],
        'store_plates': LogisticsBridge.SPECS['store_plates'],
        'check': ((), (), 'Read the factory. Checking still consumes one decision interval.'),
        'wait': ((), (), 'Take no action this interval. Takes no arguments. The runner advances exactly 15 simulated seconds after EVERY decision, including invalid actions.'),
    }

    def action(self, action):
        if not isinstance(action, dict) or set(action) != {'tool', 'args'} or not isinstance(action['args'], dict):
            raise ValueError('Use exactly {"tool":"name","args":{...}}')
        name, args = action['tool'], action['args']
        if not isinstance(name, str) or name not in self.SPECS:
            raise ValueError('Maintenance has no finish tool. Choose: '+', '.join(self.SPECS))
        if set(args) != set(self.SPECS[name][1]):
            raise ValueError(f'{name} requires exactly {list(self.SPECS[name][1])}')
        if name == 'wait':
            return {'idle': True, 'simulation_advancement': 'runner_owned'}
        if name == 'fuel':
            count = args['coal_count']
            if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 3:
                raise ValueError('Maintenance coal_count must be an integer 1..3')
        return super().action(action)

    def observation(self):
        observation = super().observation()
        live = self._json(self._actor()+'''
local result={};
for _,entity in pairs(actor.surface.find_entities_filtered{name={'burner-mining-drill','stone-furnace'},position=actor.position,radius=100}) do
 local burner=entity.burner;
 table.insert(result,{name=entity.name,position=entity.position,
 coal_in_fuel_inventory=burner.inventory.get_item_count('coal'),
 remaining_burning_fuel_joules=burner.remaining_burning_fuel,
 currently_burning=burner.currently_burning and burner.currently_burning.name or false});
end; rcon.print(helpers.table_to_json(result));''')
        if live == {}:
            live = []
        by_position = {(e['name'], e['position']['x'], e['position']['y']): e for e in live}
        for entity in observation['equipment']:
            key = (entity['name'], entity['position']['x'], entity['position']['y'])
            if key in by_position:
                entity['burner'] = {k: v for k, v in by_position[key].items() if k not in ('name', 'position')}
        return observation


class ProductionMonitor:
    """Nonoverlapping exact 60-second windows; two bad windows mean sustained failure."""
    def __init__(self, start_tick, start_plates, target=16):
        self.start_tick = start_tick
        self.start_plates = start_plates
        self.target = target
        self.low_streak = 0
        self.windows = []

    def sample(self, tick, plates):
        elapsed = tick-self.start_tick
        if elapsed < 3600:
            return None
        if elapsed != 3600:
            raise RuntimeError('Production window must be exactly 3600 ticks; cadence was violated')
        count = plates-self.start_plates
        if count < 0:
            raise RuntimeError('Production counter decreased during the evaluation')
        self.low_streak = self.low_streak+1 if count < self.target else 0
        window = {'index': len(self.windows), 'start_tick': self.start_tick, 'end_tick': tick,
                  'actual_ticks': elapsed, 'iron_plates': count, 'target': self.target,
                  'below_target': count < self.target, 'consecutive_low_windows': self.low_streak}
        self.windows.append(window)
        self.start_tick, self.start_plates = tick, plates
        return window

    @property
    def failed(self):
        return self.low_streak >= 2


def build_maintenance_fixture(instance, state_text):
    """Scripted setup excluded from model actions and production measurements."""
    from fle.commons.models.game_state import GameState
    instance.reset(game_state=GameState.parse_raw(state_text))
    instance.game_control.pause()
    bridge = MaintenanceBridge(instance, game_speed=10, carry_limit=100)
    # Construction uses the same validated logistics interface, with normal fuel
    # quantities. The maintenance toolset is frozen only after setup.
    setup = LogisticsBridge(instance, game_speed=10, carry_limit=100)
    events = []

    def call(tool, **args):
        action = {'tool': tool, 'args': args}
        result = setup.action(action)
        events.append({'action': action, 'result': result, 'tick': setup.tick()})
        return result

    ore = call('find_iron')
    call('move', position=ore)
    drill = call('place_drill', position=ore, direction='RIGHT')
    furnace = call('place_furnace_at_output', drill_handle=drill['handle'])
    chest = call('place_storage', position={'x': ore['x']-3, 'y': ore['y']-3})
    for entity in (drill, furnace):
        call('fuel', building_handle=entity['handle'], coal_count=3)
    warmup = call('wait', seconds=60)
    if warmup['iron_plates'] < 16 or warmup['ticks'] != 3600:
        raise RuntimeError('Maintenance fixture failed its reachable-production warm-up')
    # Direct output geometry and fresh visible handles, not injected ore.
    bridge.observation()
    return bridge, {'kind': 'scripted_setup_excluded_from_model', 'events': events,
                    'warmup': warmup, 'initial_fuel_per_machine': 3,
                    'fixture_entities': [drill, furnace, chest]}
