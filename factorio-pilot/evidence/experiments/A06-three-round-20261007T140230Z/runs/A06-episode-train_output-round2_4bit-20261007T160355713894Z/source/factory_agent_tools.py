"""Development-only small task interface; preserve the measured pilot adapter."""
import json
import time
from game_bridge import GameBridge

class FactoryBridge(GameBridge):
    SPECS = {
        'find_iron': ((), (), 'Find the nearest iron deposit. Returns {x,y}.'),
        'move': (('position',), ('position',), 'Move close to a position before building. position is {x,y}.'),
        'place_drill': (('position','direction'), ('position','direction'), 'Place one supplied burner drill over iron. direction is RIGHT, LEFT, UP or DOWN; choose RIGHT for a simple layout. Position is {x,y}; placement snaps to valid nearby tiles.'),
        'place_furnace_at_output': (('drill_handle',), ('drill_handle',), 'Place one supplied furnace directly adjacent to the specified drill output. The adapter calculates the adjacent geometry. Use a returned drill handle such as e1.'),
        'fuel': (('building_handle','coal_count'), ('building_handle','coal_count'), 'Insert supplied coal into the specified drill or furnace. coal_count is integer 1..50. You already have coal: do not mine it. Fuel EACH machine with 50 coal.'),
        'check': ((), (), 'Read equipment, fuel, ore/plate inventory and production.'),
        'wait': (('seconds',), ('seconds',), 'Advance 1..60 simulated seconds. After building/fueling, wait 60 to measure plate production.'),
        'finish': ((), (), 'Request completion. Accepted only when the latest 60-second wait produced at least 16 plates; the runner then independently evaluates two more windows.'),
    }

    def __init__(self, instance, visual=False, game_speed=10):
        super().__init__(instance)
        self.last_test = None
        self.visual = visual
        self.game_speed = game_speed

    def advance(self, seconds):
        if not self.visual:
            return super().advance(seconds)
        if isinstance(seconds,bool) or not isinstance(seconds,int) or not 1<=seconds<=60:
            raise ValueError('seconds must be an integer 1..60')
        before = self.tick()
        self.instance.rcon_client.send_command(f'/sc game.speed={self.game_speed}; game.tick_paused=true; game.ticks_to_run={seconds*60}')
        deadline = time.monotonic()+seconds/self.game_speed+20
        while time.monotonic()<deadline:
            actual = self.tick()-before
            if actual == seconds*60:
                return actual
            if actual > seconds*60:
                raise RuntimeError('Visual simulation overshot its tick budget')
            time.sleep(.1)
        raise TimeoutError('Visual simulation advancement timed out')

    def prompt(self):
        return '\n'.join(f'{name}: args={list(allowed)}, required={list(required)}. {doc}' for name,(allowed,required,doc) in self.SPECS.items())

    def observation(self):
        raw = super().observation()
        # Raw FLE warnings were unreliable in the reachability control. Preserve
        # raw observations in the run log; give the model concrete inventories.
        entities = [{k:v for k,v in entity.items() if k in
                     ('handle','name','position','direction','status','fuel','furnace_source','furnace_result','drop_position')}
                    for entity in raw['entities'] if isinstance(entity,dict)]
        return {'inventory':{k:v for k,v in raw['inventory'].items() if k in ('coal','burner-mining-drill','stone-furnace')},
                'equipment':entities,'production':raw['production'],
                'last_production_test':self.last_test}

    def action(self, action):
        if not isinstance(action,dict) or set(action)!= {'tool','args'} or not isinstance(action['args'],dict):
            raise ValueError('Use exactly {"tool":"name","args":{...}}. args must be a JSON object.')
        name,args = action['tool'],action['args']
        if not isinstance(name,str) or name not in self.SPECS:
            raise ValueError('Unknown tool. Choose one of: '+', '.join(self.SPECS))
        allowed,required,_ = self.SPECS[name]
        if set(args)-set(allowed) or set(required)-set(args):
            raise ValueError(f'{name} requires {list(required)} and accepts only {list(allowed)}')
        if name == 'check':
            return self.observation()
        if name == 'finish':
            if not self.last_test or self.last_test['seconds']!=60 or self.last_test['iron_plates']<16:
                raise ValueError('Factory is not verified. Place a furnace at the drill output, fuel BOTH machines, then wait 60 seconds and produce at least 16 plates before finish.')
            return {'done':True}
        if name == 'wait':
            before = self.instance.namespace._get_production_stats()
            ticks = self.advance(args['seconds'])
            after = self.instance.namespace._get_production_stats()
            self.last_test = {'seconds':args['seconds'],'ticks':ticks,
                              'iron_plates':after['output'].get('iron-plate',0)-before['output'].get('iron-plate',0)}
            return self.last_test
        if name == 'find_iron':
            translated = {'tool':'nearest','args':{'type':'IronOre'}}
        elif name == 'move':
            if self.visual:
                self.instance.game_control.set_speed_and_unpause(self.game_speed)
                try:
                    return self.describe(self.instance.namespace.move_to(self.convert('position',args['position'])))
                finally:
                    self.instance.game_control.pause()
            translated = {'tool':'move_to','args':args}
        elif name == 'place_drill':
            translated = {'tool':'place_entity','args':{'entity':'BurnerMiningDrill',**args,'exact':False}}
        elif name == 'place_furnace_at_output':
            handle = args['drill_handle']
            if not isinstance(handle,str) or handle not in self.handles or self.handles[handle].name!='burner-mining-drill':
                raise ValueError('drill_handle must be an existing burner drill handle, such as e1')
            drill = self.handles[handle]
            direction = str(drill.direction).split('.')[-1]
            translated = {'tool':'place_entity_next_to','args':{'entity':'StoneFurnace',
                'reference_position':{'x':drill.position.x,'y':drill.position.y},'direction':direction,'spacing':0}}
        elif name == 'fuel':
            handle,count = args['building_handle'],args['coal_count']
            if not isinstance(handle,str) or handle not in self.handles or self.handles[handle].name not in ('burner-mining-drill','stone-furnace'):
                raise ValueError('building_handle must be a returned drill or furnace handle, such as e1')
            if isinstance(count,bool) or not isinstance(count,int) or not 1<=count<=50:
                raise ValueError('coal_count must be an integer 1..50')
            translated = {'tool':'insert_item','args':{'entity':'Coal','target':handle,'quantity':count}}
        # Mutations invalidate an earlier completion test. All underlying
        # actions still go through the original validated adapter.
        if name in ('place_drill','place_furnace_at_output','fuel'):
            self.last_test = None
        return super().action(translated)
