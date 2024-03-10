# blankie.modules.remote_receiver
# Receives events from buses and manages remote sessions.
# Unlike remote_sender, we only need one instance in total.

import threading

import blankie
import blankie.server
import blankie.session

class RemoteReceiverModule(blankie.module.Module):
	name = 'remote_receiver'

	def __init__(self):
		super().__init__()

	def bus_packet(self, packet):
		match packet['type']:
			case 'message':
				instance_id = packet['id']
				session_spec = ('session.remote', instance_id)

				if session_spec not in blankie.session.session_specs:
					blankie.session.attach(session_spec)

					session = blankie.module.get(session_spec)
					session.bus_packet(packet)

			case 'disconnect':
				# TODO: does not handle multiple buses correctly
				remote_session_specs = [spec for spec in blankie.session.session_specs if spec[0] == 'session.remote']
				for spec in remote_session_specs:
					blankie.session.detach(spec)

			case 'leave':
				instance_id = packet['id']
				session_spec = ('session.remote', instance_id)
				if session_spec in blankie.session.session_specs:
					blankie.session.detach(session_spec)
