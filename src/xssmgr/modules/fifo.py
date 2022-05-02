# xssmgr.modules.fifo - core on_start module
# Receives events from a POSIX FIFO filesystem object.
# Needed for daemon communication commands such as "xssmgr stop" or
# "xssmgr status".

import contextlib
import os
import threading

import xssmgr
import xssmgr.fifo
from xssmgr.logging import log

class FIFOModule(xssmgr.modules.Module):
	name = 'fifo'

	def __init__(self):
		# reader thread
		self.fifo_reader_thread = None

	def start(self):
		# Check if xssmgr is already running.
		# (TODO - not translating old implementation from bash to Python)

		# Remove stale FIFO
		with contextlib.suppress(FileNotFoundError):
			os.remove(xssmgr.fifo.path)
			log.debug('mod_fifo: Removed stale FIFO: %s', xssmgr.fifo.path)

		# Create the event funnel FIFO
		os.mkfifo(xssmgr.fifo.path, mode=0o600)

		# Run reader thread
		self.fifo_reader_thread = threading.Thread(target=self.fifo_reader, daemon=True)
		self.fifo_reader_thread.start()

	def stop(self):
		# TODO - we can't interrupt the blocking 'open' easily.
		# Run the reader thread as daemon for now, and let it get
		# killed automatically.

		# Delete FIFO. We are no longer accepting commands.
		os.remove(xssmgr.fifo.path)

	def fifo_reader(self):
		while True:
			try:
				with open(xssmgr.fifo.path, 'rb') as f:
					command_str = f.readline().rstrip(b'\n')
			except FileNotFoundError:
				log.debug('mod_fifo: FIFO gone - stopping.')
				return

			log.trace('mod_fifo: Got string: %s', command_str)
			command = eval(command_str)  # TODO
			xssmgr.daemon.call(_run_command, *command)


# Handle one command received from the FIFO.
def _run_command(*args):
	log.debug('mod_fifo: Got command: %s', str(args))
	match args[0]:
		case 'ping':
			with open(args[1], 'wb') as f:
				f.write(b'pong\n')
		case 'status':
			with open(args[1], 'w', encoding='utf-8') as f:
				f.write('Currently locked: %s\n' % (xssmgr.state.locked,))
				f.write('Running modules:\n')
				f.write(''.join('- %s\n' % (m,) for m in xssmgr.modules.running_modules))
				xssmgr.config.configurator.print_status(f)
		case 'stop':
			xssmgr.daemon.stop()
		case 'reload':
			xssmgr.config.reload()
		case 'module': # Synchronously execute module subcommand, in the daemon process
			xssmgr.modules.get(args[1]).fifo_command(*args[2:])
		case 'lock':
			log.security('mod_fifo: Locking the screen due to user request.')
			if not xssmgr.state.locked:
				xssmgr.lock()
				with open(args[1], 'wb') as f: f.write(b'Locked.\n')
			else:
				with open(args[1], 'wb') as f: f.write(b'Already locked.\n')
		case 'unlock':
			log.security('mod_fifo: Unlocking the screen due to user request.')
			if xssmgr.state.locked:
				xssmgr.unlock()
				with open(args[1], 'wb') as f: f.write(b'Unlocked.\n')
			else:
				with open(args[1], 'wb') as f: f.write(b'Already unlocked.\n')
		case _:
			log.warning('mod_fifo: Ignoring unknown daemon command: %s', str(args))
