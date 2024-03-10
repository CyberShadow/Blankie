# blankie.modules.bus_client - optional on_start module
# Connects to a Blankie bus, and allows receiving and sending messages to it.

import hashlib
import json
import socket
import time
import threading
import uuid

import blankie

class BusClientModule(blankie.module.Module):
	name = 'bus_client'

	def __init__(self, address):
		super().__init__()

		self.address = address
		self.instance_id = uuid.uuid4()

		self.socket = None
		self.thread = None

		# Controls whether the thread should keep running.
		self.running = False

	def start(self):
		self.running = True
		self.thread = threading.Thread(target=self.thread_func)
		self.thread.start()

	def stop(self):
		self.running = False

		# TODO: Do we need a mutex?
		if self.socket is not None:
			self.socket.shutdown(socket.SHUT_RDWR)
			self.socket.close()
			self.socket = None

		if self.thread is not None:
			self.thread.join()
			self.thread = None

	def thread_func(self):
		while self.running:
			try:
				self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
				self.socket.connect(self.address)
				self.log.trace('Connected to bus.')

				try:
					for line in self.socket.makefile():
						self.log.trace('Received bus packet: %r', line)
						packet = json.loads(line.strip())
						blankie.daemon.call(self.handle_packet, packet)
				finally:
					s = self.socket
					self.socket = None
					s.close()

					blankie.daemon.call(self.handle_disconnect)

			except Exception as e:
				if self.running:
					self.log.warning('Bus client error: %s', e)
					time.sleep(1)
				else:
					self.log.trace('Bus client error (disconnected): %s', e)

	def handle_packet(self, packet):
		if packet['type'] == 'challenge':
			bus_key = blankie.config.configurator.bus_key
			assert bus_key is not None, 'Bus key is not configured'

			challenge = bytes.fromhex(packet['challenge'])
			digest = hashlib.sha256(bus_key + challenge).hexdigest()

			self.send({
				'type': 'hello',
				'digest' : digest,
				'id': str(self.instance_id),
			})
			return

		for module_spec in blankie.module.running_modules:
			blankie.module.get(module_spec).bus_packet(packet)

	def handle_disconnect(self):
		self.handle_packet({'type': 'disconnect'})

	def send(self, packet):
		try:
			packet_json = json.dumps(packet)
			self.log.trace('Sending bus packet: %r', packet_json)
			self.socket.send((packet_json + "\n").encode())
			return True
		except Exception as e:
			self.log.trace('Failed to send bus packet: %s', e)
			return False

	def send_message(self, message):
		self.send({
			'type': 'message',
			'message': message,
		})
