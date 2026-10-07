"""Restricted plate collection/storage, with exact inventory conservation."""
import json
import math
from factory_agent_tools import FactoryBridge
from game_bridge import GameBridge

class LogisticsBridge(FactoryBridge):
    SPECS = {
        **FactoryBridge.SPECS,
        'place_storage': (('position',),('position',),'Place one supplied wooden chest near {x,y}. Returns a chest handle. A nearby chest does not automatically collect furnace output.'),
        'collect_output': (('furnace_handle','plate_count'),('furnace_handle','plate_count'),'Move finished normal iron plates from the exact furnace OUTPUT into the agent inventory. plate_count is integer 1..100; transfers up to available plates and free carrying space. Stand within 10 tiles. Never inserts ore or plates into a furnace.'),
        'store_plates': (('chest_handle','plate_count'),('chest_handle','plate_count'),'Move carried normal iron plates into the exact wooden chest. plate_count is integer 1..100; transfers up to carried plates and free chest space. Stand within 10 tiles. Full destinations return an error; no items are destroyed.'),
        'finish': ((),(),'Request completion only after the latest 60-second test reaches the configured production target. The runner independently evaluates two more windows.'),
    }

    def __init__(self,instance,visual=False,game_speed=10,target_plate_rate=16,carry_limit=100):
        super().__init__(instance,visual,game_speed)
        if target_plate_rate not in (16,32) or isinstance(carry_limit,bool) or not isinstance(carry_limit,int) or not 1<=carry_limit<=1000:
            raise ValueError('Unsupported production target or carried-plate limit')
        self.target_plate_rate=target_plate_rate
        self.carry_limit=carry_limit
        self.agent_index=int(instance.namespace.agent_index)+1

    def _actor(self):
        return f'''local actor=storage.agent_characters[{self.agent_index}];
if not actor or not actor.valid then error('Agent character is unavailable') end;
local carried=actor.get_main_inventory();
if not carried or not carried.valid then error('Agent inventory is unavailable') end;'''

    def _json(self,lua):
        response=self.instance.rcon_client.send_command('/sc '+lua)
        try: return json.loads(response.strip())
        except json.JSONDecodeError as exc: raise RuntimeError('Inventory operation failed: '+response.strip()) from exc

    def storage_status(self):
        return self._json(self._actor()+f'''
local item={{name='iron-plate',quality='normal'}};
local count=carried.get_item_count(item);
local result={{agent_index={self.agent_index},carried_plates=count,carried_chests=carried.get_item_count('wooden-chest'),inventory_slots=#carried,
physical_plate_space=carried.get_insertable_count(item),
benchmark_carried_plate_limit={self.carry_limit},
available_carry_space=math.max(0,math.min(carried.get_insertable_count(item),{self.carry_limit}-count)),stores={{}}}};
for _,entity in pairs(actor.surface.find_entities_filtered{{name={{'stone-furnace','wooden-chest'}},position=actor.position,radius=100}}) do
 local inv=entity.name=='stone-furnace' and entity.get_output_inventory() or entity.get_inventory(defines.inventory.chest);
 table.insert(result.stores,{{name=entity.name,position=entity.position,slots=#inv,
iron_plates=inv.get_item_count(item),free_plate_capacity=inv.get_insertable_count(item)}});
end; rcon.print(helpers.table_to_json(result));''')

    def observation(self):
        observation=super().observation()
        status=self.storage_status()
        stores=status.pop('stores')
        if stores=={}: stores=[]
        by_position={(e['name'],e['position']['x'],e['position']['y']):e for e in stores}
        for entity in observation['equipment']:
            key=(entity['name'],entity['position']['x'],entity['position']['y'])
            if key in by_position:
                entity['output_storage']={k:v for k,v in by_position[key].items() if k not in ('name','position')}
        observation['inventory']['iron-plate']=status['carried_plates']
        observation['inventory']['wooden-chest']=status['carried_chests']
        observation['carrying']=status
        observation['goal_plates_per_minute']=self.target_plate_rate
        return observation

    def _transfer(self,entity,quantity,collect):
        if entity.name not in ('stone-furnace','wooden-chest'):
            raise ValueError('Unsupported transfer entity')
        x,y=float(entity.position.x),float(entity.position.y)
        if not all(math.isfinite(v) and abs(v)<=500 for v in (x,y)):
            raise ValueError('Invalid observed entity position')
        source='machine' if collect else 'carried'
        destination='carried' if collect else 'machine'
        inventory='entity.get_output_inventory()' if collect else 'entity.get_inventory(defines.inventory.chest)'
        capacity=f'math.max(0,{self.carry_limit}-carried.get_item_count(item))' if collect else 'math.huge'
        result=self._json(self._actor()+f'''
if not game.tick_paused or game.ticks_to_run~=0 then error('Transfer requires paused simulation') end;
local entity=actor.surface.find_entity('{entity.name}',{{x={x!r},y={y!r}}});
if not entity or not entity.valid then error('Observed building no longer exists') end;
if entity.force~=actor.force then error('Building belongs to another force') end;
local dx=actor.position.x-entity.position.x; local dy=actor.position.y-entity.position.y;
if dx*dx+dy*dy>100 then error('Move within 10 tiles of the building') end;
local machine={inventory}; local item={{name='iron-plate',quality='normal'}};
local source={source}; local destination={destination};
local before_source=source.get_item_count(item); local before_destination=destination.get_item_count(item);
local count=math.min({quantity},before_source,destination.get_insertable_count(item),{capacity});
local moved=0;
if count>0 then
 local removed=source.remove{{name='iron-plate',quality='normal',count=count}};
 moved=destination.insert{{name='iron-plate',quality='normal',count=removed}};
 if moved<removed then
  local restored=source.insert{{name='iron-plate',quality='normal',count=removed-moved}};
  if restored~=removed-moved then error('Incomplete inventory rollback') end;
 end;
end;
local after_source=source.get_item_count(item); local after_destination=destination.get_item_count(item);
if before_source-after_source~=moved or after_destination-before_destination~=moved then error('Inventory conservation failed') end;
rcon.print(helpers.table_to_json({{requested={quantity},transferred=moved,source_before=before_source,source_after=after_source,
destination_before=before_destination,destination_after=after_destination,item='iron-plate',quality='normal',conserved=true}}));''')
        if result['transferred']==0:
            raise ValueError('No plates moved: source is empty or destination/carrying capacity is full. Inspect storage and collect/store in a different order.')
        return result

    def action(self,action):
        if not isinstance(action,dict) or set(action)!= {'tool','args'} or not isinstance(action['args'],dict):
            raise ValueError('Use exactly {"tool":"name","args":{...}}')
        name,args=action['tool'],action['args']
        if name=='finish' and (not self.last_test or self.last_test['seconds']!=60 or self.last_test['iron_plates']<self.target_plate_rate):
            raise ValueError(f'Latest production test must reach {self.target_plate_rate} plates per minute; inspect bottlenecks or add another fueled drill/furnace chain.')
        if name not in ('place_storage','collect_output','store_plates'):
            return super().action(action)
        required=self.SPECS[name][1]
        if set(args)!=set(required): raise ValueError(f'{name} requires exactly {list(required)}')
        if name=='place_storage':
            self.last_test=None
            return GameBridge.action(self,{'tool':'place_entity','args':{'entity':'WoodenChest','position':args['position'],'exact':False}})
        key='furnace_handle' if name=='collect_output' else 'chest_handle'
        handle,count=args[key],args['plate_count']
        kind='stone-furnace' if name=='collect_output' else 'wooden-chest'
        if not isinstance(handle,str) or handle not in self.handles or self.handles[handle].name!=kind:
            raise ValueError(f'{key} must be a returned {kind} handle')
        if isinstance(count,bool) or not isinstance(count,int) or not 1<=count<=100:
            raise ValueError('plate_count must be an integer 1..100')
        return self._transfer(self.handles[handle],count,name=='collect_output')
