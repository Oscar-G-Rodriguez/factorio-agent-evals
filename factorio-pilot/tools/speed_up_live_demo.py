"""Bounded live switch for the already-running normal-speed demonstration."""
import time
from factorio_rcon import RCONClient
client=RCONClient('127.0.0.1',27000,'factorio')
deadline=time.monotonic()+45
while time.monotonic()<deadline:
    client.send_command('/sc game.speed=10')
    time.sleep(.2)
client.close()
print('Live development simulation switched to 10x; automatic tick limits preserved.')
