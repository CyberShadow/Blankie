# blankie.__init__ - core definitions and logic
# Receives events and manages X screen saver settings, power,
# and the screen locker.

import math
import os
import sys

# -----------------------------------------------------------------------------
# External globals - made available to the configuration and external processes

# This session's runtime directory.  Modules may put state here.
run_dir = os.environ.setdefault(
	'BLANKIE_RUN_DIR',
	os.getenv(
		'XDG_RUNTIME_DIR',
		'/tmp/' + str(os.getuid())
	) + '/blankie'
)

# -----------------------------------------------------------------------------
# Internal globals

# Allow running Blankie directly from a source checkout or extracted
# tarball.
is_source_checkout = __file__.endswith('/src/blankie/__init__.py')

# Library directory.
if is_source_checkout:
	# Running from a source checkout
	lib_dir = os.path.dirname(__file__) + '/../../lib'
else:
	lib_dir = '/usr/lib/blankie'

# -----------------------------------------------------------------------------
# Current state

# These encode the current state of the system, which is used to
# select which modules should be running.
class State:
	# Do we want the lock screen to be active right now?
	# Modified by the lock module, as well as the lock/unlock commands.
	locked = False

	# True when the system is about to go to sleep (or otherwise be
	# incapacitated).
	sleeping = False

	def __str__(self):
		return 'is locked: %s, sleeping: %s' % (
			self.locked,
			self.sleeping,
		)

state = State()

# Return the point in time since the system was active,
# as a number of seconds since the UNIX epoch.
# This function may return one of two special values:
# - math.inf: when the system, in its current state,
#   cannot become idle, no matter how much time will pass.
# - -math.inf: when the system is about to go to sleep
#   (or otherwise be incapacitated)
def get_idle_since():
	if state.sleeping:
		return math.inf
	return max((session.get_idle_since() for session in blankie.session.get_sessions()),
			   default=math.inf)

# -----------------------------------------------------------------------------
# Locking

# Note: the lock state can be affected by multiple sources - not just
# the lock module, but also the explicit lock/unlock actions.  This
# should work "as expected", so the lock module only changes the lock
# state on edge (its own start and stop), as opposed to enforcing it
# for the entire duration it's running.

def lock():
	state.locked = True
	blankie.config.reconfigure()

# Pipes to processes waiting for a notification for when the lock screen exits.
unlock_notification_fds = []

def unlock():
	state.locked = False

	# Ensure we don't try to immediately relock / go to sleep
	for session in blankie.session.get_sessions():
		session.invalidate()

	# Notify of unlocks.
	global unlock_notification_fds
	for locker_reply_fd in unlock_notification_fds:
		locker_reply_fd.write('Unlocked\n')
		locker_reply_fd.close()
	unlock_notification_fds = []

	blankie.config.reconfigure()

# -----------------------------------------------------------------------------
# Exceptions

# Represents an expected failure mode, which is unlikely to be due to
# a bug in Blankie.  In this case, we do not need to print an exception
# stack trace; just print the error message and quit.
class UserError(Exception):
	pass

# -----------------------------------------------------------------------------
# Import Blankie modules
# Placed after the declarations above, so that they can be used by the
# imported modules.

import blankie.config
import blankie.daemon
import blankie.server
import blankie.module
import blankie.session
from blankie.logging import log

# -----------------------------------------------------------------------------
# Core functionality: run core modules

is_systemd = False
try:
	is_systemd = os.readlink('/bin/init').endswith('/systemd')
except Exception:
	pass
if is_systemd:
	log.debug('Detected systemd - enabling systemd-logind integration')

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
	if is_systemd:
		wanted_modules.append(
			# Connects to D-Bus to intercept the system going to sleep.
			# Required to reliably lock the system first.
			('logind',)
		)

blankie.module.selectors['10-core'] = core_selector

# -----------------------------------------------------------------------------
# Entry point

def main():
	args = sys.argv[1:]

	help_text = '''
Usage: blankie COMMAND

Commands:
  help         Print this message.
  start        Start the blankie daemon.
  stop         Stop the blankie daemon.
  status       Print the current status.
  reload       Reload the configuration.
  lock         Lock the system now.
  unlock       Unlock the system now.
  attach       Attach to the current session.
  detach       Detach from the current session.
'''

	if not args:
		sys.stderr.write(help_text)
		return 2

	try:
		os.makedirs(run_dir, exist_ok=True)
		blankie.config.load()

		match args[0]:
			case 'help':
				sys.stdout.write(help_text)

			case 'start':
				ret = blankie.daemon.start()
				if ret != 0:
					return ret

				session_spec = blankie.session.get_session()
				if session_spec is not None:
					log.info('Automatically attaching to current session %s.', session_spec)
					blankie.session.remote_attach_or_detach(True, session_spec)

			case 'stop':
				blankie.daemon.stop_remote()

			case 'reload':
				blankie.server.notify(*args)

			case 'status' | 'lock' | 'unlock':
				sys.stdout.buffer.write(blankie.server.query(*args))

			case 'attach' | 'detach':
				blankie.session.remote_attach_or_detach(args[0] == 'attach')

			# Internal commands:
			case 'module':
				blankie.module.cli_command(args[1:])

			case _:
				log.critical('Unknown command: %r', args[0])
				return 1

		return 0

	except UserError as e:
		log.critical('Fatal error: %s', e)
		return 1
