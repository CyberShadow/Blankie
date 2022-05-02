# xssmgr.modules.fifo - core on_start module
# Receives events from a POSIX FIFO filesystem object.
# Needed for daemon communication commands such as "xssmgr stop" or
# "xssmgr status".

import contextlib
import os
import threading

import xssmgr
import xssmgr.fifo
from xssmgr.util import *

class FIFOModule(xssmgr.Module):
	name = 'fifo'

	def __init__(self):
		# reader thread
		self.reader_thread = None

	def start(self):
		# Check if xssmgr is already running.
		# (TODO - not translating old implementation from bash to Python)

		# Remove stale FIFO
		with contextlib.suppress(FileNotFoundError):
			os.remove(xssmgr.fifo.path)
			logv('mod_fifo: Removed stale FIFO: %s', xssmgr.fifo.path)

		# Create the event funnel FIFO
		os.mkfifo(xssmgr.fifo.path, mode=0o600)

		# Run reader thread
		self.reader_thread = threading.Thread(target=self._reader, daemon=True)
		self.reader_thread.start()

	def stop(self):
		# TODO - we can't interrupt the blocking 'open' easily.
		# Run the reader thread as daemon for now, and let it get
		# killed automatically.

		# Delete FIFO. We are no longer accepting commands.
		os.remove(xssmgr.fifo.path)

	def _reader(self):
		while True:
			try:
				with open(xssmgr.fifo.path, 'rb') as f:
					command_str = f.readline().rstrip(b'\n')
			except FileNotFoundError:
				logv('mod_fifo: FIFO gone - stopping.')
				return

			command = eval(command_str)  # TODO
			xssmgr.daemon.call(_run_command, *command)


# Handle one command received from the FIFO.
def _run_command(*args):
	logv('mod_fifo: Got command: %s', str(args))
	match args[0]:
		case 'ping':
			with open(args[1], 'wb') as f:
				f.write(b'pong\n')
		case 'status':
			with open(args[1], 'w', encoding='utf-8') as f:
				f.write('Currently locked: %d\n' % (xssmgr.locked))
				f.write('Running modules:\n')
				f.write(''.join('- %s\n' % m for m in xssmgr.running_modules))
				f.write('Configured on_start modules:\n')
				f.write(''.join('- %s\n' % m for m in xssmgr.config.configurator.on_start_modules))
				f.write('Configured on_idle modules:\n')
				f.write(''.join('- %d %s\n' % m for m in xssmgr.config.configurator.on_idle_modules))
				f.write('Configured on_lock modules:\n')
				f.write(''.join('- %s\n' % m for m in xssmgr.config.configurator.on_lock_modules))
		case 'stop':
			xssmgr.daemon.stop()
		case 'reload':
			xssmgr.config.reload()
		case 'module': # Synchronously execute module subcommand, in the daemon process
			xssmgr.get_module(args[1]).fifo_command(*args[2:])
		case 'lock':
			log('mod_fifo: Locking the screen due to user request.')
			if not xssmgr.locked:
				xssmgr.lock()
				with open(args[1], 'wb') as f: f.write('Locked.\n')
			else:
				with open(args[1], 'wb') as f: f.write('Already locked.\n')
		case 'unlock':
			log('mod_fifo: Unlocking the screen due to user request.')
			if xssmgr.locked:
				xssmgr.unlock()
				with open(args[1], 'wb') as f: f.write('Unlocked.\n')
			else:
				with open(args[1], 'wb') as f: f.write('Already unlocked.\n')
		case _:
			log('mod_fifo: Ignoring unknown daemon command: %s', str(args))
