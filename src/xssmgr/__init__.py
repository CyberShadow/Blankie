# xssmgr.__init__ - core definitions and logic
# Receives events and manages X screen saver settings, power,
# and the screen locker.

import hashlib
import importlib
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

# Log verbosity setting.
verbose = int(os.getenv('XSSMGR_VERBOSE', '0'))

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
# Core module machinery

# Map from module instance IDs to module names + parameters.
modules = {}

# Module search path.  Populated in load_config.
module_dirs = []

# Currently running modules.
running_modules = []

# Functions to call to build the list of modules which should be
# running right now.
# Functions are called in order of this associative array's keys.
module_selectors = {}

def load_module(module_name):
	for module_dir in module_dirs:
		module_file = module_dir  + '/' + module_name + '.py'
		if os.path.exists(module_file):
			logv('Loading module \'%s\' from \'%s\'', module_name, module_file)
			python_module_name = 'xssmgr.modules' + module_name

			# https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly
			spec = importlib.util.spec_from_file_location(python_module_name, module_file)
			module = importlib.util.module_from_spec(spec)
			sys.modules[module_name] = module
			spec.loader.exec_module(module)

			# Pull in module function definitions into our global namespace.
			# TODO: maintain a dict instead.
			for name, value in vars(module).items():
				if name.startswith('mod_'):
					globals()[name] = value

			return

	raise Exception('Module \'%s\' not found (looked in: %s)' % (
		module_name,
		str(module_dirs),
	))

# By default, a module instance is identified by the module name + its
# parameters.  However, some modules require custom identification
# logic, when some of their parameters should be allowed to change
# without xssmgr restarting the module.
# This function registers the module instance (saving its full
# parameters) and outputs its ID in the homonym variable, running any
# custom logic if present.
def get_module_id(module_name, *module_args_):
	global module_args
	module_args = module_args_

	module_func = 'mod_' + module_name
	if module_func not in globals():
		logv('Auto-loading module \'%s\'', module_name)
		load_module(module_name)

	module = (module_name, *module_args)

	# Non-local
	global module_id
	module_id = 'dummy_id'

	globals()[module_func]('hash')

	if module_id == 'dummy_id':
		# Use default hashing logic
		module_id = hashlib.sha1(bytes(str(module), 'utf-8')).hexdigest()

	modules[module_id] = module
	return module_id

# A module instance is identified by its ID, as generated and saved in
# module_id.
def module_command(module_id_, *arguments):
	global module_id
	module_id = module_id_

	module_arr = modules[module_id]

	module_name = module_arr[0]
	# Modules can read and parse their parameters from this variable.
	global module_args
	module_args = module_arr[1:]

	module_func = 'mod_' + module_name
	# At this point, the function is expected to have already been
	# loaded in module_id.
	# logv('Calling %s with %s', module_func, arguments)
	globals()[module_func](*arguments)

# Start or stop modules, synchronizing running_modules
# against wanted_modules.
def start_stop_modules():
	# logv('Running modules:%s', ''.join('\n- ' + m for m in running_modules))
	# logv('Wanted  modules:%s', ''.join('\n- ' + m for m in wanted_modules))

	# Because modules may themselves start or stop other modules when
	# they are started or stopped, support recursion by performing one
	# operation at a time, and recursing to restart the loop until
	# there is no work left to be done.

	# 1. Stop modules which we no longer want to be running.
	# Do this in reverse order of starting them.
	for i, running_module in reversed(list(enumerate(running_modules))):
		if running_module not in wanted_modules:
			del running_modules[i]
			logv('Stopping module %s', str(modules[running_module]))
			module_command(running_module, 'stop')
			logv('Stopped module %s', str(modules[running_module]))
			return start_stop_modules()  # Recurse

	# 2. Start modules which we now want to be running.
	for wanted_module in wanted_modules:
		if wanted_module not in running_modules:
			running_modules.append(wanted_module)
			logv('Starting module: %s', str(modules[wanted_module]))
			module_command(wanted_module, 'start')
			logv('Started module: %s', str(modules[wanted_module]))
			return start_stop_modules()  # Recurse

	# If we reached this point, there is no more work to do.
	logv('Modules are synchronized.')

# Start or stop modules according to the current circumstances.
def update_modules():
	# 1. Build the list of wanted modules.
	# Do this by calling the functions registered in module_selectors.

	logv('Updating list of modules to run with circumstances: is locked: %s, is idle: %s, idle time: %s',
		 locked, idle, idle_time)

	global wanted_modules
	wanted_modules = []

	for key in sorted(module_selectors.keys()):
		module_selector = module_selectors[key]
		# logv('Calling module selector: %s', module_selector)
		module_selector()

	# 2. Start/stop modules accordingly.
	start_stop_modules()

# -----------------------------------------------------------------------------
# Current state
# These encode the current state of the system, which is used to
# select which modules should be running.

# Whether we are currently idle (according to X / xss).
# Because xss is affected by X screen-saver inhibitors,
# this may be 0 even if xprintidle would produce a large number.
idle = 0

# X server idle time (as provided by xprintidle), in milliseconds,
# or max_time
idle_time = 0

# Lock screen active right now?
locked = False

# Constant - dummy idle time used for when the system is about to go to sleep
# TODO: use math.inf
max_time = float('inf')

# -----------------------------------------------------------------------------
# Communication globals, used to store additional values passed between functions.
# These should be refactored away.

# List built by module selectors to choose which modules should be
# running at the moment.
# TODO: refactor out
wanted_modules = None

# Instance ID of the currently invoked module.
# TODO: refactor out
module_id = None

# Arguments of the currently invoked module.
# TODO: refactor out
module_args = None

# Global dynamic state.
# Artifact of literal bash -> Python translation, will be deleted.
global_state = {}

# -----------------------------------------------------------------------------
# Core functionality: run core modules

def core_selector():
	wanted_modules.extend([
		# Receives commands / events from other processes.
		get_module_id('fifo'),

		# Configures the X screensaver, so that we receive idle /
		# unidle events.
		get_module_id('xset'),

		# Receives idle / unidle events.
		get_module_id('xss'),
	])

	if idle:
		# Wakes us up when it's time to run the next on_idle hook(s).
		wanted_modules.append(get_module_id('timer'))

module_selectors['10-core'] = core_selector

# -----------------------------------------------------------------------------
# Locking

# Note: the lock state can be affected by multiple sources - not just
# the lock module, but also the explicit lock/unlock actions.  This
# should work "as expected", so the lock module only changes the lock
# state on edge (its own start and stop), as opposed to enforcing it
# for the entire duration it's running.

def lock():
	global locked
	locked = True
	xssmgr.config.reconfigure()

# Pipes to processes waiting for a notification for when the lock screen exits.
unlock_notification_fds = []

def unlock():
	global locked, idle_time
	locked = False
	idle_time = 0  # Ensure we don't try to immediately relock / go to sleep

	# Notify of unlocks.
	global unlock_notification_fds
	for locker_reply_fd in unlock_notification_fds:
		locker_reply_fd.write('Unlocked\n')
		locker_reply_fd.close()
	unlock_notification_fds = []

	xssmgr.config.reconfigure()

# -----------------------------------------------------------------------------
# Entry point

import xssmgr.config
import xssmgr.daemon
import xssmgr.fifo
from xssmgr.util import *

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
			sys.stdout.write(xssmgr.fifo.query(*args))

		# Internal commands:
		case 'module':
			# Synchronously instantiate a module and execute a module
			# subcommand, outside the daemon process.
			module = args[1]
			module_arr = eval(module)  # TODO

			module_command(get_module_id(*module_arr), args[2:])

		case _:
			log('Unknown command: %s', str(args))
			sys.exit(1)
