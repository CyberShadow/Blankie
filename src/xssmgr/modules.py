# xssmgr.modules - core module machinery

import importlib
import os
import traceback

import xssmgr
from xssmgr.util import *

# Base class for modules.
class Module:
	# All modules should define their name.
	name = None

	# Constructor. You can specify module parameters as its signature.
	def __init__(self):
		pass

	# Start function.  If called, stop() will also be called exactly once.
	# All resource acquisition and initialization should happen here.
	def start(self):
		pass

	# Stop function.  Called if start() was called.
	def stop(self):
		pass

	# Optional reconfiguration function.
	# Should accept the same arguments as the constructor.
	# Will be called on a running (started) module when xssmgr wants
	# to stop and start a pair of modules with the same name
	# (differing only in parameters).
	# - If it returns True, the reconfiguration is considered to have
	#   been successful, and the module is now considered to be an
	#   instance corresponding to the new parameters.
	# - If it returns False, the old instance is stopped and a new
	#   instance is started instead.
	def reconfigure(self, *_args, **_kwargs):
		return False

	# Run an 'xssmgr module ...' command.
	# (Runs outside the daemon process.)
	def cli_command(self, *_args):
		raise NotImplementedError()

	# Handle a message received from the FIFO.
	def fifo_command(self, *_args):
		raise NotImplementedError()

# Module search path.  Populated in load_config.
module_dirs = []

# Currently running modules.
running_modules = []

# Functions to call to build the list of modules which should be
# running right now.
# Functions are called in order of this associative array's keys.
selectors = {}

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

			return

	raise Exception('Module \'%s\' not found (looked in: %s)' % (
		module_name,
		str(module_dirs),
	))

# Map from module specs to Module instances.
module_instances = {}

def get(module_spec):
	if module_spec in module_instances:
		return module_instances[module_spec]

	module_name = module_spec[0]
	module_classes = [c for c in Module.__subclasses__() if c.name == module_name]
	if len(module_classes) == 0:
		logv('Auto-loading module \'%s\'', module_name)
		load_module(module_name)
		module_classes = [c for c in Module.__subclasses__() if c.name == module_name]

	assert len(module_classes) > 0, "No module class defined with name == '%s'" % (module_name,)
	assert len(module_classes) == 1, "More than one module class defined with name == '%s'" % (module_name,)
	module_class = module_classes[0]

	# Instantiate
	module = module_class(*module_spec[1:])
	module_instances[module_spec] = module
	return module

# Start or stop modules, synchronizing running_modules
# against wanted_modules.
def start_stop_modules():
	# logv('Running modules:%s', ''.join('\n- ' + m for m in running_modules))
	# logv('Wanted  modules:%s', ''.join('\n- ' + m for m in wanted_modules))

	# Because modules may themselves start or stop other modules when
	# they are started or stopped, support recursion by performing one
	# operation at a time, and recursing to restart the loop until
	# there is no work left to be done.

	# 1. Reconfigure modules which can be reconfigured.
	for wanted_module in xssmgr.wanted_modules:
		if wanted_module not in running_modules:
			for i, running_module in enumerate(running_modules):
				if wanted_module[0] == running_module[0] and \
				   running_module not in xssmgr.wanted_modules:
					module = get(running_module)
					result = module.reconfigure(*wanted_module[1:])
					if result:
						running_modules[i] = wanted_module
						del module_instances[running_module]
						module_instances[wanted_module] = module
						logv('Reconfigured module %s from %s to %s.',
							 wanted_module[0], running_module[1:], wanted_module[1:])
						return start_stop_modules()  # Recurse

	# 2. Stop modules which we no longer want to be running.
	# Do this in reverse order of starting them.
	for i, running_module in reversed(list(enumerate(running_modules))):
		if running_module not in xssmgr.wanted_modules:
			del running_modules[i]
			logv('Stopping module %s', str(running_module))
			# It is important that, in case of an error, we revert
			# back to the original state insofar as possible.
			# This means that an error in one module should not cause
			# us to not try to stop other modules.
			module = get(running_module)
			try:
				module.stop()
			except Exception:
				log('Error when attempting to stop module %s:', str(running_module))
				traceback.print_exc()
				xssmgr.exit_code = 1
			logv('Stopped module %s', str(running_module))
			return start_stop_modules()  # Recurse

	# 3. Start modules which we now want to be running.
	for wanted_module in xssmgr.wanted_modules:
		if wanted_module not in running_modules:
			running_modules.append(wanted_module)
			logv('Starting module: %s', str(wanted_module))
			get(wanted_module).start()
			logv('Started module: %s', str(wanted_module))
			return start_stop_modules()  # Recurse

	# If we reached this point, there is no more work to do.
	logv('Modules are synchronized.')

# Start or stop modules according to the current circumstances.
def update():
	# 1. Build the list of wanted modules.
	# Do this by calling the functions registered in selectors.

	logv('Updating list of modules to run with circumstances: is locked: %s, is idle: %s, idle time: %s',
		 xssmgr.locked, xssmgr.idle, xssmgr.idle_time)

	xssmgr.wanted_modules = []

	for key in sorted(selectors.keys()):
		selector = selectors[key]
		# logv('Calling module selector: %s', selector)
		selector()

	# 2. Start/stop modules accordingly.
	start_stop_modules()