"""Bounded FLE helper save preparation; retains runtime backups, never recurses.

Only two verified function-only helper tables and four named FLE helper functions
leave persistent storage. Actors, queues, inventories and other values remain.
"""
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import factorio_rcon
from a06_fixture_controls import physical_snapshot

ROOT_HELPERS = {'clear_lua_script_checksums', 'get_alerts',
                'get_lua_script_checksums', 'set_lua_script_checksum'}


class RawBridge:
    def __init__(self, client, backup=False):
        self.client = client
        self.backup = backup

    def _actor(self):
        return 'local actor=storage.agent_characters[1]; local carried=actor.get_main_inventory();'

    def _json(self, lua):
        if self.backup:
            lua = lua.replace('storage.utils.get_contents_compat', '_G.a06_native_helpers_backup.utils.get_contents_compat')
        return json.loads(self.client.send_command('/sc ' + lua))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['prepare', 'restore'])
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    run = args.run.resolve()
    if not run.name.startswith('A06-train_drill-controls-'):
        raise ValueError('Unexpected fixture run')
    inventory = json.loads((run / 'storage_function_inventory.json').read_text())
    allowed_roots = {'storage.' + key for key in ROOT_HELPERS}
    if any(not (p.startswith('storage.actions.') or p.startswith('storage.utils.') or p in allowed_roots)
           for p in inventory['paths']):
        raise RuntimeError('A function exists outside the reviewed helper fields')
    tables = {t['path']: t for t in inventory['tables']}
    for name in ('storage.actions', 'storage.utils'):
        if tables[name]['scalar_count'] != 0 or tables[name]['table_count'] != 0:
            raise RuntimeError('Helper table contains state; refuse to replace it')
    client = factorio_rcon.RCONClient('127.0.0.1', 27000, os.environ.get('FACTORIO_RCON_PASSWORD', 'factorio'))
    client.connect()
    if args.mode == 'prepare':
        before = physical_snapshot(RawBridge(client))
        response = client.send_command('''/sc if not game.tick_paused or game.ticks_to_run~=0 then error('Preparation requires paused game') end;
if _G.a06_native_helpers_backup then error('Helper backup already exists') end;
for _,t in pairs({storage.actions,storage.utils}) do
 for _,v in pairs(t) do if type(v)~='function' then error('Helper table has persistent state') end end;
end;
for _,name in pairs({'clear_lua_script_checksums','get_alerts','get_lua_script_checksums','set_lua_script_checksum'}) do
 if type(storage[name])~='function' then error('Named helper not present') end;
end;
_G.a06_native_helpers_backup={actions=storage.actions,utils=storage.utils,
 clear_lua_script_checksums=storage.clear_lua_script_checksums,get_alerts=storage.get_alerts,
 get_lua_script_checksums=storage.get_lua_script_checksums,set_lua_script_checksum=storage.set_lua_script_checksum};
storage.actions={}; storage.utils={};
storage.clear_lua_script_checksums=nil; storage.get_alerts=nil;
storage.get_lua_script_checksums=nil; storage.set_lua_script_checksum=nil;
rcon.print('PREPARED_BOUNDED_HELPERS');''')
        if response.strip() != 'PREPARED_BOUNDED_HELPERS':
            raise RuntimeError(response)
        after = physical_snapshot(RawBridge(client, backup=True))
        if before != after:
            raise RuntimeError('Physical snapshot changed during helper preparation')
        record = {'mode': args.mode, 'function_paths': inventory['paths'],
                  'physical_snapshot_unchanged': True,
                  'runtime_backup_retained': True, 'recursive_mutation': False}
    else:
        from fle.env.lua_manager import LuaScriptManager
        from fle.env.utils.rcon import _load_mods
        client.send_command('/sc ' + _load_mods('checksum'))
        manager = LuaScriptManager(client, cache_scripts=False)
        for name in ('initialise', 'lualib_util', 'utils', 'alerts', 'connection_points',
                     'recipe_fluid_connection_mappings', 'serialize', 'serialize_direction_fix'):
            manager.load_init_into_game(name)
        names = sorted({str(Path(name).parent.name) for name in manager.tool_scripts})
        for name in names:
            manager.load_tool_into_game(name)
        record = {'mode': args.mode, 'physical_snapshot': physical_snapshot(RawBridge(client)),
                  'restored_from_installed_sources': True, 'tool_names': names}
    record['source_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    source_name = 'a06_save_helpers-' + record['source_sha256'] + '.py'
    record['source_snapshot'] = 'source/' + source_name
    (run / ('helpers_' + args.mode + '_' + stamp + '.json')).write_text(json.dumps(record, indent=2) + '\n')
    (run / 'source' / source_name).write_bytes(Path(__file__).read_bytes())
    print('HELPERS_' + args.mode.upper() + '_VERIFIED')


if __name__ == '__main__':
    main()
