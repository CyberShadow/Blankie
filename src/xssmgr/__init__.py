# xssmgr.__init__ - core definitions and logic
# Receives events and manages X screen saver settings, power,
# and the screen locker.

import math
import os
import sys

# -----------------------------------------------------------------------------
# External globals - made available to the configuration and external processes

# This session's runtime directory.  Modules may put state here.
run_dir = os.environ.setdefault(
	'XSSMGR_RUN_DIR',
	os.getenv(
		'XDG_RUNTIME_DIR',
		'/tmp/' + str(os.getuid())
	) + '/xssmgr'
)

# -----------------------------------------------------------------------------
# Internal globals

# Allow running xssmgr directly from a source checkout or extracted
# tarball.
is_source_checkout = __file__.endswith('/src/xssmgr/__init__.py')

# Library directory.
if is_source_checkout:
	# Running from a source checkout
	lib_dir = os.path.dirname(__file__) + '/../../lib'
else:
	lib_dir = '/usr/lib/xssmgr'

# -----------------------------------------------------------------------------
# Current state

# These encode the current state of the system, which is used to
# select which modules should be running.
class State:
	# Do we want the lock screen to be active right now?
	# Modified by the lock module, as well as the lock/unlock commands.
	locked = False

	def __str__(self):
		return 'is locked: %s' % (
			self.locked
		)

state = State()

def get_idle_time():
	return min((session.get_idle_time() for session in xssmgr.session.get_sessions()),
			   default=-math.inf)

# -----------------------------------------------------------------------------
# Locking

# Note: the lock state can be affected by multiple sources - not just
# the lock module, but also the explicit lock/unlock actions.  This
# should work "as expected", so the lock module only changes the lock
# state on edge (its own start and stop), as opposed to enforcing it
# for the entire duration it's running.

def lock():
	state.locked = True
	xssmgr.config.reconfigure()

# Pipes to processes waiting for a notification for when the lock screen exits.
unlock_notification_fds = []

def unlock():
	state.locked = False

	# Ensure we don't try to immediately relock / go to sleep
	for session in xssmgr.session.get_sessions():
		session.invalidate()

	# Notify of unlocks.
	global unlock_notification_fds
	for locker_reply_fd in unlock_notification_fds:
		locker_reply_fd.write('Unlocked\n')
		locker_reply_fd.close()
	unlock_notification_fds = []

	xssmgr.config.reconfigure()

# -----------------------------------------------------------------------------
# Exceptions

# Represents an expected failure mode, which is unlikely to be due to
# a bug in xssmgr.  In this case, we do not need to print an exception
# stack trace; just print the error message and quit.
class UserError(Exception):
	pass

# -----------------------------------------------------------------------------
# Import xssmgr modules
# Placed after the declarations above, so that they can be used by the
# imported modules.

import xssmgr.config
import xssmgr.daemon
import xssmgr.server
import xssmgr.module
import xssmgr.session
from xssmgr.logging import log

# -----------------------------------------------------------------------------
# Core functionality: run core modules

def core_selector(wanted_modules):
	wanted_modules.extend([
		# Receives commands / events from other processes.
		('server', ),

		# Receives idle / unidle events from X.
		# Required for X11 sessions to work properly.
		('xss', ),

		# Monitors TTY device timestamps.
		# Required for TTY sessions to work properly.
		('tty_idle', ),
	])

xssmgr.module.selectors['10-core'] = core_selector

# -----------------------------------------------------------------------------
# Entry point

def main():
	args = sys.argv[1:]

	if not args:
		sys.stderr.write('''
Usage: xssmgr COMMAND

Commands:
  start        Start the xssmgr daemon.
  stop         Stop the xssmgr daemon.
  status       Print the current status.
  reload       Reload the configuration.
  lock         Lock the X session now.
  unlock       Unlock the X session now.
''')
		return 2

	try:
		os.makedirs(run_dir, exist_ok=True)
		xssmgr.config.load()

		match args[0]:
			case 'start':
				ret = xssmgr.daemon.start()
				if ret != 0:
					return ret

				session_spec = xssmgr.session.get_session()
				if session_spec is not None:
					log.info('Automatically attaching to current session %s.', session_spec)
					xssmgr.session.remote_attach_or_detach(True, session_spec)

			case 'stop':
				xssmgr.daemon.stop_remote()

			case 'reload':
				xssmgr.server.notify(*args)

			case 'status' | 'lock' | 'unlock':
				sys.stdout.buffer.write(xssmgr.server.query(*args))

			case 'attach' | 'detach':
				xssmgr.session.remote_attach_or_detach(args[0] == 'attach')

			# Internal commands:
			case 'module':
				xssmgr.module.cli_command(args[1:])

			case _:
				log.critical('Unknown command: %r', args[0])
				return 1

		return 0

	except UserError as e:
		log.critical('Fatal error: %s', e)
		return 1
