# xssmgr.modules.fifo - core on_start module
# Receives events from a POSIX FIFO filesystem object.
# Needed for daemon communication commands such as "xssmgr stop" or
# "xssmgr status".

import contextlib
import os
import threading
import types

import xssmgr
import xssmgr.fifo
from xssmgr.util import *

def mod_fifo(*args):
	# Private state:
	s = xssmgr.global_state.setdefault(xssmgr.module_spec, types.SimpleNamespace(

		# reader thread
		reader = None,
	))

	# Implementation:

	match args[0]:
		case 'start':
			# Check if xssmgr is already running.
			# (TODO - not translating old implementation from bash to Python)

			# Remove stale FIFO
			with contextlib.suppress(FileNotFoundError):
				os.remove(xssmgr.fifo.path)
				logv('mod_fifo: Removed stale FIFO: %s', xssmgr.fifo.path)

			# Create the event funnel FIFO
			os.mkfifo(xssmgr.fifo.path, mode=0o600)

			# Run reader thread
			s.reader = threading.Thread(target=fifo_reader, daemon=True)
			s.reader.start()

		case 'stop':
			# TODO - we can't interrupt the blocking 'open' easily.
			# Run the reader thread as daemon for now.

			# Delete FIFO. We are no longer accepting commands.
			os.remove(xssmgr.fifo.path)


def fifo_reader():
	while True:
		try:
			with open(xssmgr.fifo.path, 'rb') as f:
				command_str = f.readline().rstrip(b'\n')
		except FileNotFoundError:
			logv('mod_fifo: FIFO gone - stopping.')
			return

		command = eval(command_str)  # TODO
		xssmgr.daemon.call(run_command, *command)


# Handle one command received from the FIFO.
def run_command(*args):
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
			xssmgr.module_command(*args[1:])
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
