# blankie.modules.server - core on_start module
# Runs a UNIX socket server and receives events.
# Needed for daemon communication commands such as "blankie stop" or
# "blankie status".

import contextlib
import json
import os
import socketserver
import threading

import blankie
import blankie.server
import blankie.session

class ServerModule(blankie.module.Module):
	name = 'server'

	def __init__(self):
		super().__init__()

		# SocketServer instance.
		self.server = None

		# Thread running the server accept loop.
		self.server_thread = None

	def start(self):
		# Remove stale socket
		with contextlib.suppress(FileNotFoundError):
			os.remove(blankie.server.path)
			self.log.debug('Removed stale socket: %r', blankie.server.path)

		# Create and initialize the SocketServer instance
		self.server = SocketServer(self)

		# Run reader thread
		self.server_thread = threading.Thread(target=self.server_thread_func)
		self.server_thread.start()

	def stop(self):
		# We can't directly interrupt the blocking 'accept' easily,
		# but we can send a dummy command which will cause the server
		# to check if it should shut down.
		self.server.stopping = True
		self.server = None
		blankie.server.notify('server-shutdown-ping')

		# Now, just wait for the thread to exit.
		self.server_thread.join()
		self.server_thread = None

	def server_thread_func(self):
		server = self.server

		while not server.stopping:
			server.handle_request()
		self.log.debug('Stopping server thread.')

	def server_reader(self, handler):
		command_str = handler.rfile.readline()

		if not command_str.endswith(b'\n'):
			self.log.warning('Received unterminated command: %r', command_str)
			return
		command_str = command_str[:-1]

		self.log.trace('Got string: %r', command_str)
		command = json.loads(command_str)

		if command == ['server-shutdown-ping']:
			return  # This was sent just to wake up the accept loop.

		done_event = threading.Event()
		blankie.daemon.call(self.server_run_command, handler, done_event, *command)

		# Wait until the event is processed, to avoid the connection
		# getting closed early.
		done_event.wait()

	# Handle one command received from the socket.
	# Runs in the main thread.
	def server_run_command(self, handler, done_event, *args):
		try:
			self.log.debug('Got command: %r', args)
			match args[0]:
				case 'ping':
					handler.wfile.write(b'pong\n')
				case 'status':
					handler.wfile.write(b'Currently locked: %r\n' % (blankie.state.locked,))
					handler.wfile.write(b'Running modules:\n')
					handler.wfile.write(b''.join(b'- %r\n' % (m,) for m in blankie.module.running_modules))
					blankie.config.configurator.print_status(handler.wfile)
				case 'stop':
					blankie.daemon.stop()
				case 'reload':
					blankie.config.reload()
				case 'module': # Synchronously execute module subcommand, in the daemon process
					blankie.module.get(args[1]).server_command(*args[2:])
				case 'lock':
					self.log.security('Locking the screen due to user request.')
					if not blankie.state.locked:
						blankie.lock()
						handler.wfile.write(b'Locked.\n')
					else:
						handler.wfile.write(b'Already locked.\n')
				case 'unlock':
					self.log.security('Unlocking the screen due to user request.')
					if blankie.state.locked:
						blankie.unlock()
						handler.wfile.write(b'Unlocked.\n')
					else:
						handler.wfile.write(b'Already unlocked.\n')
				case 'attach':
					try:
						blankie.session.attach(args[1:])
						handler.wfile.write(b'ok')
					except Exception as e:
						handler.wfile.write(bytes(str(e), encoding="utf-8"))
				case 'detach':
					try:
						blankie.session.detach(args[1:])
						handler.wfile.write(b'ok')
					except Exception as e:
						handler.wfile.write(bytes(str(e), encoding="utf-8"))
				case _:
					self.log.warning('Ignoring unknown daemon command: %r', args)
		finally:
			done_event.set()

# Glue between socketserver and ServerModule.

class Handler(socketserver.StreamRequestHandler):
	def handle(self):
		self.server.module.server_reader(self)

class SocketServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
	def __init__(self, module):
		self.module = module
		self.stopping = False
		super().__init__(blankie.server.path, Handler)
