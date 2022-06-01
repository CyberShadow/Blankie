# xssmgr.modules.server - core on_start module
# Runs a UNIX socket server and receives events.
# Needed for daemon communication commands such as "xssmgr stop" or
# "xssmgr status".

import contextlib
import json
import os
import socketserver
import threading

import xssmgr
import xssmgr.server
import xssmgr.session

class ServerModule(xssmgr.module.Module):
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
			os.remove(xssmgr.server.path)
			self.log.debug('Removed stale socket: %r', xssmgr.server.path)

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
		xssmgr.server.notify('server-shutdown-ping')

		# Now, just wait for the thread to exit.
		self.server_thread.join()
		self.server_thread = None

	def server_thread_func(self):
		server = self.server

		while not server.stopping:
			server.handle_request()
		self.log.debug('Stopping server thread.')

	def server_reader(self, rfile, wfile):
		command_str = rfile.readline()

		if not command_str.endswith(b'\n'):
			self.log.warning('Received unterminated command: %r', command_str)
			return
		command_str = command_str[:-1]

		self.log.trace('Got string: %r', command_str)
		command = json.loads(command_str)

		if command == ['server-shutdown-ping']:
			return  # This was sent just to wake up the accept loop.

		done_event = threading.Event()
		xssmgr.daemon.call(self.server_run_command, rfile, wfile, done_event, *command)

		# Wait until the event is processed, to avoid the connection
		# getting closed early.
		done_event.wait()

	# Handle one command received from the socket.
	# Runs in the main thread.
	def server_run_command(self, rfile, wfile, done_event, *args):
		try:
			self.log.debug('Got command: %r', args)
			match args[0]:
				case 'ping':
					wfile.write(b'pong\n')
				case 'status':
					wfile.write(b'Currently locked: %r\n' % (xssmgr.state.locked,))
					wfile.write(b'Running modules:\n')
					wfile.write(b''.join(b'- %r\n' % (m,) for m in xssmgr.module.running_modules))
					xssmgr.config.configurator.print_status(wfile)
				case 'stop':
					xssmgr.daemon.stop()
				case 'reload':
					xssmgr.config.reload()
				case 'module': # Synchronously execute module subcommand, in the daemon process
					xssmgr.module.get(args[1]).server_command(*args[2:])
				case 'lock':
					self.log.security('Locking the screen due to user request.')
					if not xssmgr.state.locked:
						xssmgr.lock()
						wfile.write(b'Locked.\n')
					else:
						wfile.write(b'Already locked.\n')
				case 'unlock':
					self.log.security('Unlocking the screen due to user request.')
					if xssmgr.state.locked:
						xssmgr.unlock()
						wfile.write(b'Unlocked.\n')
					else:
						wfile.write(b'Already unlocked.\n')
				case 'attach':
					try:
						xssmgr.session.attach(args[1:])
						wfile.write(b'ok')
					except Exception as e:
						wfile.write(e)
				case 'detach':
					try:
						xssmgr.session.detach(args[1:])
						wfile.write(b'ok')
					except Exception as e:
						wfile.write(e)
				case _:
					self.log.warning('Ignoring unknown daemon command: %r', args)
		finally:
			done_event.set()

# Glue between socketserver and ServerModule.

class Handler(socketserver.StreamRequestHandler):
	def handle(self):
		self.server.module.server_reader(self.rfile, self.wfile)

class SocketServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
	def __init__(self, module):
		self.module = module
		self.stopping = False
		super().__init__(xssmgr.server.path, Handler)
