"""A small JSON-to-FLE adapter. Model text is never evaluated as Python."""
import inspect
import math
import time
from fle.env import Direction
from fle.env.entities import Position, Entity
from fle.env.game_types import Prototype, Resource

TOOLS = ('inspect_inventory', 'nearest', 'move_to', 'place_entity',
         'place_entity_next_to', 'get_entity', 'get_entities', 'insert_item',
         'rotate_entity', 'can_place_entity', 'pickup_entity')
PROTOTYPES = ('BurnerMiningDrill', 'StoneFurnace', 'BurnerInserter',
              'WoodenChest', 'TransportBelt', 'Coal', 'IronOre', 'IronPlate')

class GameBridge:
    def __init__(self, instance):
        self.instance = instance
        self.handles = {}
        self.identities = {}

    def tick(self):
        return int(self.instance.rcon_client.send_command('/sc rcon.print(game.tick)').strip())

    def advance(self, seconds):
        if isinstance(seconds, bool) or not isinstance(seconds, int) or not 1 <= seconds <= 60:
            raise ValueError('wait seconds must be an integer from 1 to 60')
        ticks = seconds * 60
        before = self.tick()
        self.instance.rcon_client.send_command(
            f'/sc game.speed=10; game.tick_paused=true; game.ticks_to_run={ticks}')
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            actual = self.tick() - before
            if actual == ticks:
                return actual
            if actual > ticks:
                raise RuntimeError('Simulation overshot controlled tick budget.')
            time.sleep(0.05)
        raise TimeoutError('Controlled simulation timed out.')

    def describe(self, value):
        if isinstance(value, Entity):
            key = (value.name, value.position.x, value.position.y)
            handle = self.identities.setdefault(key, f'e{len(self.identities) + 1}')
            self.handles[handle] = value
            result = {'handle': handle, 'name': value.name,
                      'position': {'x': value.position.x, 'y': value.position.y}}
            for name in ('direction', 'status', 'inventory', 'fuel', 'warnings',
                         'drop_position', 'pickup_position', 'output_position',
                         'fuel_inventory', 'furnace_source', 'furnace_result'):
                if hasattr(value, name):
                    field = getattr(value, name)
                    result[name] = self.describe(field) if isinstance(field, (Position, dict)) else str(field)[:1500]
            return result
        if isinstance(value, Position):
            return {'x': value.x, 'y': value.y}
        if isinstance(value, (list, tuple)):
            return [self.describe(item) for item in value]
        if isinstance(value, dict):
            return {str(key): self.describe(item) for key, item in value.items()}
        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        return str(value)

    def convert(self, key, value, tool_name=None):
        if key in ('position', 'reference_position'):
            if not isinstance(value, dict) or set(value) != {'x', 'y'}:
                raise ValueError(f'{key} must contain numeric x and y')
            if any(isinstance(n, bool) or not isinstance(n, (int, float)) or
                   not math.isfinite(n) or abs(n) > 500 for n in value.values()):
                raise ValueError('Coordinates must be finite and within 500 tiles')
            return Position(**value)
        if key in ('entity', 'entities'):
            if tool_name in ('rotate_entity', 'pickup_entity') and key == 'entity':
                if value not in self.handles:
                    raise ValueError(f'Unknown entity handle: {value}')
                return self.handles[value]
            def prototype(name):
                if name not in PROTOTYPES:
                    raise ValueError(f'Unsupported prototype: {name}')
                return getattr(Prototype, name)
            return {prototype(name) for name in value} if key == 'entities' and isinstance(value, list) else prototype(value)
        if key == 'type':
            if value not in ('IronOre', 'Coal', 'Stone'):
                raise ValueError('nearest type must be IronOre, Coal, or Stone')
            return getattr(Resource, value)
        if key == 'direction':
            if value not in ('UP', 'RIGHT', 'DOWN', 'LEFT'):
                raise ValueError('direction must be UP, RIGHT, DOWN, or LEFT')
            return getattr(Direction, value)
        if key == 'target':
            if value not in self.handles:
                raise ValueError(f'Unknown entity handle: {value}')
            return self.handles[value]
        if key in ('quantity', 'spacing', 'radius'):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 500:
                raise ValueError(f'{key} must be between 0 and 500')
            return value
        if key == 'exact' and isinstance(value, bool):
            return value
        raise ValueError(f'Unsupported argument: {key}')

    def action(self, action):
        if not isinstance(action, dict) or set(action) != {'tool', 'args'}:
            raise ValueError('Response must have exactly tool and args')
        name, arguments = action['tool'], action['args']
        if not isinstance(arguments, dict):
            raise ValueError('args must be an object')
        if name == 'done':
            if arguments:
                raise ValueError('done takes no arguments')
            return {'done': True}
        if name == 'wait':
            if set(arguments) != {'seconds'}:
                raise ValueError('wait takes seconds only')
            return {'advanced_ticks': self.advance(arguments['seconds'])}
        if name not in TOOLS:
            raise ValueError(f'Unknown tool: {name}')
        tool = getattr(self.instance.namespace, name)
        converted = {key: self.convert(key, value, name) for key, value in arguments.items()}
        inspect.signature(tool).bind(**converted)
        # Movement requests need the game's asynchronous pathfinder to tick.
        # This action's physical time is measured, rather than assumed fixed.
        if name == 'move_to':
            self.instance.game_control.set_speed_and_unpause(10)
            try:
                return self.describe(tool(**converted))
            finally:
                self.instance.game_control.pause()
        return self.describe(tool(**converted))

    def observation(self):
        return {'inventory': self.describe(dict(self.instance.namespace.inspect_inventory())),
                'entities': self.describe(self.instance.namespace.get_entities(radius=100)),
                'production': self.instance.namespace._get_production_stats(),
                'game_tick': self.tick()}

    def prompt(self):
        docs = []
        for name in TOOLS:
            tool = getattr(self.instance.namespace, name)
            # Namespace tools are wrapped functions, with docs on the function.
            docs.append(f'{name}{inspect.signature(tool)}\n{inspect.getdoc(tool)}')
        return '\n\n'.join(docs)
