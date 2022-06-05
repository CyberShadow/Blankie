# blankie.server - UNIX socket management and sending commands
# The daemon will listen on a UNIX socket (see the 'server' module)
# which allows it to receive commands from other processes.

import json
import os
import socket

import blankie

# Path to the UNIX socket filesystem object.
path = os.environ.setdefault('XSSMGR_SOCKET', blankie.run_dir + '/daemon.sock')

# -----------------------------------------------------------------------------
# Daemon communication

# Send a line to the daemon event loop. Return the socket without closing it.
def _send(*args):
	s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
	try:
		s.connect(path)
	except (FileNotFoundError, ConnectionRefusedError) as e:
		raise blankie.UserError('Failed to connect to daemon UNIX socket at %r (%s). Is the blankie daemon running?' %
							   (path, e))

	message = bytes(json.dumps(args) + '\n', 'utf-8')
	s.send(message)

	return s

# Send a line to the daemon event loop
def notify(*args):
	s = _send(*args)
	s.close()

# Send a line to the daemon, and wait for a reply
def query(*args):
	s = _send(*args)
	s.shutdown(socket.SHUT_WR)

	with s.makefile('rb') as f:
		result = f.read()
	s.close()
	return result
