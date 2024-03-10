# blankie.modules.session.remote - Remote session
# Represents another connected blankie instance.

import threading
import time
import math

import blankie

class RemoteSession(blankie.session.Session):
	name = 'session.remote'

	def __init__(self, instance_id):
		super().__init__()
		self.instance_id = instance_id
		self.idle_since = math.nan

	def get_idle_since(self):
		return self.idle_since

	def bus_packet(self, packet):
		if packet['type'] == 'message':
			if packet['message']['type'] == 'idle_since':
				self.idle_since = packet['message']['idle_since']
			elif packet['message']['type'] == 'lock' and not blankie.state.locked:
				self.log.security(f'Locking (by remote instance {self.instance_id})')
				blankie.lock()
			elif packet['message']['type'] == 'unlock' and blankie.state.locked:
				self.log.security(f'Unlocking (by remote instance {self.instance_id})')
				blankie.unlock()
