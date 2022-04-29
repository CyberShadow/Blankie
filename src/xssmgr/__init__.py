# X ScreenSaver manager
# Receives events and manages X screen saver settings, power,
# and the screen locker.

import atexit
import contextlib
import os
import signal
import stat
import subprocess
import sys
import threading
import time
import types

# -----------------------------------------------------------------------------
# Usage

if len(sys.argv) == 1:
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

# -----------------------------------------------------------------------------
# External globals - made available to the configuration and modules

# Path to the xssmgr script.
os.environ['XSSMGR'] = sys.argv[0]

# This session's runtime directory.  Modules may put state here.
os.environ['XSSMGR_RUN_DIR'] = os.getenv(
	'XSSMGR_RUN_DIR',
	os.getenv(
		'XDG_RUNTIME_DIR',
		'/tmp/' + str(os.getuid())
	) + '/xssmgr-' + os.environ['DISPLAY']
)
run_dir = os.environ['XSSMGR_RUN_DIR']

# Daemon's event funnel.
os.environ['XSSMRG_FIFO'] = os.getenv('XSSMRG_FIFO', run_dir + '/daemon.fifo')
fifo = os.environ['XSSMRG_FIFO']

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

# Map from module instance IDs to module names + parameters.
modules = {}

# Module search path.  Populated in load_config.
module_dirs = []

# Currently running modules.
running_modules = []

# Modules registered in the configuration.
on_start_modules = []
on_lock_modules = []
on_idle_modules = []

# Functions to call to build the list of modules which should be
# running right now.
# Functions are called in order of this associative array's keys.
module_selectors = {}

# Whether we are currently idle (according to X / xss).
# Because xss is affected by X screen-saver inhibitors,
# this may be 0 even if xprintidle would produce a large number.
idle = 0

# X server idle time (as provided by xprintidle), in milliseconds,
# or max_time
idle_time = 0

# Constant - dummy idle time used for when the system is about to go to sleep
max_time = float('inf')

# Daemon's PID file.
pid_file = run_dir + '/daemon.pid'

# Global dynamic state.
# Artifact of literal bash -> Python translation, will be deleted.
global_state = {}

# -----------------------------------------------------------------------------
# Communication globals, used to store additional values passed between functions.
# These should be refactored away.

# List built by module selectors to choose which modules should be
# running at the moment.
wanted_modules = None

# Instance ID of the currently invoked module.
module_id = None

# Arguments of the currently invoked module.
module_args = None

# -----------------------------------------------------------------------------
# Utility functions

def log(fmt, *args):
	sys.stderr.write('xssmgr: ' + (fmt % args) + '\n')
	sys.stderr.flush()

def logv(fmt, *args):
	if verbose:
		log(fmt, *args)

# -----------------------------------------------------------------------------
# Configuration

# Called from the user's configuration to register an on-start module.
def on_start(module, *parameters):
	on_start_modules.append(get_module_id(module, *parameters))

# Called from the user's configuration to register an on-lock module.
def on_lock(module, *parameters):
	on_lock_modules.append(get_module_id(module, *parameters))

# Called from the user's configuration to register an on-idle module.
def on_idle(idle_seconds, module, *parameters):
	on_idle_modules.append((idle_seconds, get_module_id(module, *parameters)))

# (Re-)Load the configuration file.
def load_config():
	config_dirs = os.getenv('XDG_CONFIG_DIRS', '/etc').split(':')
	config_dirs = [os.getenv('XDG_CONFIG_HOME', os.environ['HOME'] + '/.config')] + config_dirs
	config_files = [d + '/xssmgr/config.py' for d in config_dirs]

	global module_dirs
	module_dirs = (
		[d + '/xssmgr/modules' for d in config_dirs] +
		[os.path.dirname(__file__) + '/modules']
	)

	for config_file in config_files:
		if os.path.exists(config_file):
			logv('Loading configuration from \'%s\'.', config_file)
			with open(config_file, 'rb') as f:
				exec(f.read(), globals())
			return

	log('WARNING: No configuration file found.')
	log('Please check installation or create \'%s\'.', config_files[0])

# -----------------------------------------------------------------------------
# Core functionality: run on_start and on_idle modules

def core_selector():
	wanted_modules.extend(on_start_modules)

	for (timeout, module) in on_idle_modules:
		if idle_time >= timeout * 1000:
			wanted_modules.append(module)
module_selectors['10-core'] = core_selector

# -----------------------------------------------------------------------------
# Built-in on_start module: xset
# Manages the X server's XScreenSaver extension settings.  Used to
# configure when xss receives notifications about the system becoming
# idle.

def mod_xset(*args):
	match args[0]:
		case 'start':
			# We configure the X screen saver to "activate" at the
			# requested idle time of the first idle hook.  Beyond
			# that, the timer module will activate and sleep until the
			# next idle hook.
			min_timeout = max_time
			max_timeout = 0
			for (timeout, _module) in on_idle_modules:
				if timeout <= 0:
					log('mod_xset: Invalid idle time: %d, ignoring', timeout)
					continue
				min_timeout = min(min_timeout, timeout)
				max_timeout = max(max_timeout, timeout)
			logv('mod_xset: Configuring X screensaver for idle hooks in the %d .. %d range.', min_timeout, max_timeout)
			if max_timeout > 0:
				subprocess.check_call(['xset', 's', str(min_timeout), '0'])
			else:
				subprocess.check_call(['xset', 's', 'off'])

		case 'stop':
			# Disable X screensaver.
			subprocess.check_call(['xset', 's', 'off'])

# -----------------------------------------------------------------------------
# Built-in on_start module: xss
# Manages an instance of a helper program, which receives screen saver
# events from the X server.  Used to know when the system becomes or
# stops being idle.

def mod_xss(*args):
	# Private state:
	s = global_state.setdefault(module_id, types.SimpleNamespace(

		# xss Popen object
		xss = None,

	))

	# Implementation:

	match args[0]:
		case 'start':
			# Start xss
			if s.xss is None:
				s.xss = subprocess.Popen(
					[lib_dir + '/xss'],
					stdout = subprocess.PIPE
				)

				if s.xss.stdout.readline() != b'init\n':
					logv('mod_xss: xss initialization failed.')
					s.xss.terminate()
					s.xss.communicate()
					s.xss = None
					raise Exception('mod_xss: Failed to start xss.')

				# Start event reader task
				threading.Thread(target=xss_reader, args=(module_id, s.xss.stdout)).start()

				logv('mod_xss: Started xss (PID %d).', s.xss.pid)

		case 'stop':
			# Stop xss
			if s.xss is not None:
				logv('mod_xss: Killing xss (PID %d)...', s.xss.pid)
				s.xss.terminate()
				s.xss.communicate()
				s.xss = None
				logv('mod_xss: Done.')

		case '_event':
			logv('mod_xss: Got line from xss: %s', str(args[1:]))
			match args[1]:
				case b'notify':
					(state, _kind, _forced) = args[2:5]
					global idle, idle_time
					if state == b'off':
						idle = 0
					else:
						idle = 1
					idle_time = int(subprocess.check_output(['xprintidle']))
					update_modules()

				case _:
					log('mod_xss: Unknown line received from xss: %s', str(args[1:]))


def xss_reader(module_id, f):
	while line := f.readline():
		notify('module', module_id, '_event', *line.split())
	logv('mod_xss: xss exited (EOF).')

# -----------------------------------------------------------------------------
# Built-in special module: lock
# Activates on_lock modules.

# Lock screen active right now?
locked = False

# React to locking/unlocking by starting/stopping on_lock modules.
def lock_selector():
	if locked:
		# Ensure lock module isn't stopped upon locking
		wanted_modules.append(get_module_id('lock'))
		wanted_modules.extend(on_lock_modules)
module_selectors['50-lock'] = lock_selector

# Additionally define a lock module, which can be added to an on_idle
# hook to lock the screen when idle.
def mod_lock(*args):
	match args[0]:
		case 'start':
			logv('mod_lock: Locking (because the lock module is being enabled).')
			lock()

		case 'stop':
			logv('mod_lock: Unlocking (because the lock module is being disabled).')
			unlock()


# Note: the lock state can be affected by multiple sources - not just
# the lock module, but also the explicit lock/unlock actions.  This
# should work "as expected", so the lock module only changes the lock
# state on edge (its own start and stop), as opposed to enforcing it
# for the entire duration it's running.

def lock():
	global locked
	locked = True
	reconfigure()

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

	reconfigure()

# -----------------------------------------------------------------------------
# Built-in special module: timer
# When active, sleeps until the next scheduled on_idle hook, and prods
# the main event loop to ensure on_idle hooks are activated
# accordingly.

def mod_timer(*args):
	# Private state:
	s = global_state.setdefault(module_id, types.SimpleNamespace(

		# Timer instance, which waits until the next event
		timer = None,

	))

	# Implementation:

	match args[0]:
		case 'start':
			timer_schedule(s)
		case 'stop':
			timer_cancel(s)
		case '_wait_done':
			logv('mod_timer: Timer fired.')
			s.timer = None  # It exited cleanly, no need to cancel it.
			global idle_time
			idle_time = int(subprocess.check_output(['xprintidle']))
			update_modules()

			timer_schedule(s)

# React to xss telling us the system became or stopped being idle.
def timer_selector():
	if idle:
		wanted_modules.append(get_module_id('timer'))
module_selectors['50-timer'] = timer_selector

def timer_cancel(s):
	if s.timer is not None:
		logv('mod_timer: Canceling old timer wait task.')
		s.timer.cancel()
		s.timer = None

def timer_schedule(s):
	timer_cancel(s)

	next_time = max_time
	for (timeout, _module) in on_idle_modules:
		timeout_ms = timeout * 1000
		if idle_time < timeout_ms < next_time:
			next_time = timeout_ms

	if next_time < max_time:
		to_sleep = next_time - idle_time + 1
		s.timer = threading.Timer(
			interval=to_sleep / 1000,
			function=notify,
			args=('module', module_id, '_wait_done')
		)
		s.timer.start()
		logv('mod_timer: Started new timer for %d milliseconds.', to_sleep)

# -----------------------------------------------------------------------------
# Daemon implementation

def load_module(module_name):
	for module_dir in module_dirs:
		module_file = module_dir  + '/' + module_name + '.py'
		if os.path.exists(module_file):
			logv('Loading module \'%s\' from \'%s\'', module_name, module_file)
			with open(module_file, 'rb') as f:
				exec(f.read(), globals())
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
		with subprocess.Popen(['sha1sum'], stdin=subprocess.PIPE, stdout=subprocess.PIPE) as p:
			(module_id, _) = p.communicate(bytes(str(module), 'utf-8'))
		module_id = module_id.split()[0]

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

# Re-evaluate the configuration and update our state to match.
def reconfigure():
	logv('Reconfiguring.')

	# Reset settings before (re-)loading configuration file.
	global on_start_modules, on_lock_modules, on_idle_modules
	on_start_modules = []
	on_lock_modules = []
	on_idle_modules = []

	# Add core modules.
	on_start_modules.append(get_module_id('xset'))
	on_start_modules.append(get_module_id('xss'))

	# Evaluate the user-defined configuration function.
	config()

	update_modules()

# Reload the configuration file and reconfigure.
def sighup():
	log('Got SIGHUP - asynchronously requesting reload.')
	# Make sure that the logic runs from the main loop, and not an
	# arbitrary place in the script.
	threading.Thread(target=notify, args=('reload')).start()


# Handle one daemon command.
def daemon_command(*args):
	match args[0]:
		case 'ping':
			with open(args[1], 'wb') as f:
				f.write(b'pong\n')
		case 'status':
			with open(args[1], 'w', encoding='utf-8') as f:
				f.write('Currently locked: %d\n' % (locked))
				f.write('Running modules:\n')
				f.write(''.join('- %s\n' % m for m in running_modules))
				f.write('Registered on_start modules:\n')
				f.write(''.join('- %s\n' % m for m in on_start_modules))
				f.write('Registered on_idle modules:\n')
				f.write(''.join('- %d %s\n' % m for m in on_idle_modules))
				f.write('Registered on_lock modules:\n')
				f.write(''.join('- %s\n' % m for m in on_lock_modules))
		case 'stop':
			log('Daemon is exiting.')
			sys.exit(0)  # Clean-up will be performed by the exit trap.
		case 'reload':
			log('Reloading configuration.')
			load_config()
			reconfigure()
		case 'module': # Synchronously execute module subcommand, in the daemon process
			module_command(*args[1:])
		case 'lock':
			log('Locking the screen due to user request.')
			if not locked:
				lock()
				with open(args[1], 'wb') as f: f.write('Locked.\n')
			else:
				with open(args[1], 'wb') as f: f.write('Already locked.\n')
		case 'unlock':
			log('Unlocking the screen due to user request.')
			if locked:
				unlock()
				with open(args[1], 'wb') as f: f.write('Unlocked.\n')
			else:
				with open(args[1], 'wb') as f: f.write('Already unlocked.\n')
		case _:
			log('Ignoring unknown daemon command: %s', str(args))

def shutdown_selector():
	wanted_modules.clear()

# Exit trap.
def daemon_shutdown():
	logv('Shutting down.')

	# Stop all modules.
	module_selectors['95-shutdown'] = shutdown_selector
	update_modules()

	# Delete FIFO. We are no longer accepting commands.
	os.remove(fifo)

	# Delete PID file. We are exiting.
	with contextlib.suppress(FileNotFoundError):
		os.remove(pid_file)

	logv('Shutdown complete, exiting.')

# Daemon main event loop.
def daemon_loop():
	# Reload the configuration when receiving a SIGHUP.
	signal.signal(signal.SIGHUP, sighup)

	# Create PID file.
	with open(pid_file, 'w') as f:
		f.write(str(os.getpid()))

	# Start on-boot modules.
	reconfigure()

	while True:
		with open(fifo, 'rb') as f:
			command_str = f.readline().rstrip(b'\n')
		command = eval(command_str)  # TODO

		logv('Got command: %s', str(command))
		daemon_command(*command)

# Daemon entry point.
def daemon():
	# Check if xssmgr is already running.
	# (TODO - not translating old implementation from bash to Python)

	# Remove stale FIFO
	with contextlib.suppress(FileNotFoundError):
		os.remove(fifo)
		logv('Removed stale FIFO: %s', fifo)

	# Ensure a clean shut-down in any eventuality.
	atexit.register(daemon_shutdown)

	# Create the event funnel FIFO
	os.mkfifo(fifo, mode=0o600)

	# Queue up a command for the daemon. If it finishes before the
	# daemon process, it has started successfully.
	ping_pid = os.fork()
	if ping_pid == 0:
		atexit.unregister(daemon_shutdown)
		sys.exit(1 - int(query('ping') == b'pong\n'))

	# Now, fork away the daemon main loop.
	daemon_pid = os.fork()
	if daemon_pid == 0:
		daemon_loop()
		assert False  # daemon_loop() does not return

	# Clear our exit trap, as it should now run in the main loop subshell.
	atexit.unregister(daemon_shutdown)

	# Wait for the daemon to finish starting up.
	(first_pid, status, _) = os.wait3(0)
	if first_pid == ping_pid and os.waitstatus_to_exitcode(status) == 0:
		log('Daemon started on %s (PID %d).',
			os.environ['DISPLAY'],
			daemon_pid)
	else:
		log('Daemon start-up failed.')
		sys.exit(1)

# -----------------------------------------------------------------------------
# Daemon communication

# Send a line to the daemon event loop
def notify(*args):
	message = bytes(str(args) + '\n', 'utf-8')
	# Send the message in one write.
	with open(fifo, 'wb') as f:
		f.write(message)

	# We do this check after writing to avoid a TOCTOU.
	if not stat.S_ISFIFO(os.stat(fifo).st_mode):
		raise Exception('\'%s\' is not a FIFO - daemon not running?' % (fifo))

# Send a line to the daemon, and wait for a reply
def query(*args):
	qfifo = run_dir + '/query.' + str(os.getpid()) + '.fifo'  # Answer will be sent here

	os.mkfifo(qfifo, mode=0o600)
	notify(*args, qfifo)
	with open(qfifo, 'rb') as f:
		result = f.read()
	os.remove(qfifo)
	return result

# -----------------------------------------------------------------------------
# Entry point

def main():
	args = sys.argv[1:]

	os.makedirs(run_dir, exist_ok=True)
	load_config()

	match args[0]:
		case 'start':
			daemon()

		case 'stop':
			if not os.path.exists(pid_file):
				log('PID file \'%s\' does not exist - daemon not running?', pid_file)
				sys.exit(2)

			with open(pid_file, 'rb') as f:
				daemon_pid = int(f.read())
			notify(*args)
			while True:
				try:
					os.kill(daemon_pid, 0)
					break
				except ProcessLookupError:
					time.sleep(0.1)
			log('Daemon stopped.')

		case 'reload':
			notify(*args)

		case 'status' | 'lock' | 'unlock':
			sys.stdout.write(query(*args))

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
