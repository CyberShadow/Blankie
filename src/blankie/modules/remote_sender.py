# blankie.modules.remote_sender
# Connects to a bus and sends information about this instance.

import threading

import blankie
import blankie.server
import blankie.session

class RemoteSenderModule(blankie.module.Module):
	name = 'remote_sender'

	def __init__(self, bus_addr):
		super().__init__()

		self.bus_client_spec = ('bus_client', bus_addr)
		self.timer = None
		self.last_idle_since = 0

	def get_dependencies(self):
		return [self.bus_client_spec]

	def start(self):
		# TODO: Replace always-on timer with some kind of hook
		# which gets called when the idle-since timestamp changes.
		self.schedule_timer()

	def schedule_timer(self):
		self.timer = threading.Timer(
			interval=5,
			function=blankie.daemon.call,
			args=(self.handle_timer,)
		)
		self.timer.start()

	def stop(self):
		if self.timer is not None:
			self.timer.cancel()
			self.timer = None

	def bus_packet(self, packet):
		if packet['type'] == 'welcome' or packet['type'] == 'join':
			self.update(True)

	def handle_timer(self):
		self.update()
		self.schedule_timer()

	def update(self, force=False):
		idle_since = blankie.get_idle_since()
		if force or self.last_idle_since != idle_since:
			message = {
				'type': 'idle_since',
				'idle_since': idle_since,
			}
			blankie.module.get(self.bus_client_spec).send_message(message)
			self.last_idle_since = idle_since
