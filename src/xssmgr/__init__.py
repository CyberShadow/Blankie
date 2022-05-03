# xssmgr.__init__ - core definitions and logic
# Receives events and manages X screen saver settings, power,
# and the screen locker.

import os
import sys

# -----------------------------------------------------------------------------
# External globals - made available to the configuration and external processes

# Path to the xssmgr script.
os.environ['XSSMGR'] = sys.argv[0]

# This session's runtime directory.  Modules may put state here.
run_dir = os.environ.setdefault(
	'XSSMGR_RUN_DIR',
	os.getenv(
		'XDG_RUNTIME_DIR',
		'/tmp/' + str(os.getuid())
	) + '/xssmgr-' + os.environ['DISPLAY']
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
	# Whether we are currently idle (according to X / xss).
	# Because xss is affected by X screen-saver inhibitors,
	# this may be False even if xprintidle would produce a large number.
	idle = False

	# X server idle time (as provided by xprintidle), in milliseconds,
	# or math.inf
	idle_time = 0

	# Do we want the lock screen to be active right now?
	# Modified by the lock module, as well as the lock/unlock commands.
	locked = False

	def __str__(self):
		return 'is locked: %s, is idle: %s, idle time: %s' % (
			self.locked, self.idle, self.idle_time
		)

state = State()

# -----------------------------------------------------------------------------
# Import xssmgr modules
# Placed after the variable declarations above, so that they can be
# used by the imported modules.

import xssmgr.config
import xssmgr.daemon
import xssmgr.fifo
import xssmgr.modules
from xssmgr.logging import log

# -----------------------------------------------------------------------------
# Core functionality: run core modules

def core_selector(wanted_modules):
	wanted_modules.extend([
		# Receives commands / events from other processes.
		('fifo', ),

		# Receives idle / unidle events.
		('xss', ),
	])

xssmgr.modules.selectors['10-core'] = core_selector

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
	state.idle_time = 0  # Ensure we don't try to immediately relock / go to sleep

	# Notify of unlocks.
	global unlock_notification_fds
	for locker_reply_fd in unlock_notification_fds:
		locker_reply_fd.write('Unlocked\n')
		locker_reply_fd.close()
	unlock_notification_fds = []

	xssmgr.config.reconfigure()

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
		sys.exit(2)

	os.makedirs(run_dir, exist_ok=True)
	xssmgr.config.load()

	match args[0]:
		case 'start':
			xssmgr.daemon.start()

		case 'stop':
			xssmgr.daemon.stop_remote()

		case 'reload':
			xssmgr.fifo.notify(*args)

		case 'status' | 'lock' | 'unlock':
			sys.stdout.buffer.write(xssmgr.fifo.query(*args))

		# Internal commands:
		case 'module':
			# Synchronously instantiate a module and execute a module
			# subcommand, outside the daemon process.
			module_spec_str = args[1]
			module_spec = eval(module_spec_str)  # TODO

			xssmgr.modules.get(module_spec).cli_command(args[2:])

		case _:
			log.critical('Unknown command: %s', str(args))
			sys.exit(1)
