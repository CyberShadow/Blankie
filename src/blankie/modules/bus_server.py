# blankie.modules.bus_server - optional on_start module
# Runs a TCP socket server for communicating with other Blankie instances.
# Does not do any logic itself, and merely passes messages around.
# All logic glue is done by the client module.

import hashlib
import json
import secrets
import socket
import threading

import blankie

class BusServerModule(blankie.module.Module):
	name = 'bus_server'

	def __init__(self, address):
		super().__init__()

		self.address = address
		self.server_socket = None
		self.accept_thread = None
		self.clients = {}

	def start(self):
		self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.server_socket.bind(self.address)
		self.server_socket.listen()

		self.accept_thread = threading.Thread(target=self.accept_loop)
		self.accept_thread.start()

	def stop(self):
		if self.server_socket is not None:
			self.server_socket.shutdown(socket.SHUT_RDWR)
			self.server_socket.close()
			self.server_socket = None

		if self.accept_thread is not None:
			self.accept_thread.join()
			self.accept_thread = None

		for client in list(self.clients.values()):
			client.stop()
		self.clients = {}

	# Runs on its own thread
	def accept_loop(self):
		while True:
			try:
				client_socket, addr = self.server_socket.accept()
				self.log.info('Accepted connection from %r', addr)
			except Exception as e:
				if self.server_socket is not None:
					self.log.warning('Error accepting connection: %s', e)
				else:
					self.log.trace('Error accepting connection (server shutting down): %s', e)
				break
			blankie.daemon.call(self.handle_socket, client_socket, addr)

	# Runs on main thread
	def handle_socket(self, client_socket, addr):
		client = ClientHandler(self, client_socket, addr)
		client.start()

	# Runs on main thread
	def broadcast(self, message, exclude=None):
		for client in self.clients.values():
			if client != exclude:
				client.send(message)

	# Runs on main thread
	def register(self, client):
		self.log.info('Registering client %r from %r', client.instance_id, client.addr)
		self.clients[client.instance_id] = client

	# Runs on main thread
	def unregister(self, client):
		del self.clients[client.instance_id]

class ClientHandler:
	# Runs on main thread
	def __init__(self, server, client_socket, addr):
		self.server = server
		self.socket = client_socket
		self.addr = addr
		self.instance_id = None
		self.recv_thread = None
		self.challenge = secrets.token_bytes(64)

	# Runs on main thread
	def start(self):
		self.recv_thread = threading.Thread(target=self.recv_loop)
		self.recv_thread.start()

	# Runs on main thread
	def stop(self):
		if self.instance_id is not None:
			self.server.unregister(self)
			self.server.broadcast({
				'type': 'leave',
				'id': self.instance_id,
			})
			self.instance_id = None

		if self.socket is not None:
			self.socket.shutdown(socket.SHUT_RDWR)
			self.socket.close()
			self.socket = None

		if self.recv_thread is not None:
			self.recv_thread.join()
			self.recv_thread = None

	# Runs on main thread
	def send(self, message):
		message_json = json.dumps(message)
		self.socket.send((message_json + "\n").encode())

	# Runs on its own thread
	def recv_loop(self):
		try:
			self.send({'type': 'challenge', 'challenge': self.challenge.hex()})

			for line in self.socket.makefile():
				packet = json.loads(line.strip())
				blankie.daemon.call(self.handle_packet, packet)
		except Exception as e:
			self.server.log.warning('Error while handling client packet: %s', e)
		blankie.daemon.call(self.stop)

	# Runs on main thread
	def handle_packet(self, packet):
		match packet['type']:
			case 'hello':
				if self.instance_id is not None:
					raise Exception('Client already identified')

				bus_key = blankie.config.configurator.bus_key
				assert bus_key is not None, 'Bus key is not configured'

				digest_expected = hashlib.sha256(bus_key + self.challenge).digest()
				digest_provided = bytes.fromhex(packet['digest'])
				ok = secrets.compare_digest(digest_expected, digest_provided)
				if not ok:
					raise Exception('Authentication failed from client %s' % self.addr)

				self.instance_id = packet['id']
				if self.instance_id in self.server.clients:
					self.server.log.warning('Duplicate client instance ID: %s', self.instance_id)
					self.server.clients[self.instance_id].stop()

				self.server.register(self)
				self.server.broadcast({
					'type': 'join',
					'id': self.instance_id,
				}, self)
				self.send({
					'type': 'welcome',
					'clients': list(self.server.clients),
				})

			case 'message':
				if self.instance_id is None:
					raise Exception('Client not identified')

				self.server.broadcast({
					'type': 'message',
					'id': self.instance_id,
					'message': packet['message'],
				}, self)

			case _:
				self.server.log.warning('Ignoring unknown bus command: %r', packet['type'])
