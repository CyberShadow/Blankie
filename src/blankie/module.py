# blankie.module - core module machinery

import importlib
import os
import shlex
import sys
import traceback

import blankie
from blankie.logging import log

# Base class for modules.
class Module:
	# All modules should define their name.
	name = None

	# Constructor. You can specify module parameters as its signature.
	def __init__(self):
		self.log = log.getChild('modules.' + self.name)

	# Start function.  If called, stop() will also be called exactly once.
	# All resource acquisition and initialization should happen here.
	def start(self):
		pass

	# Stop function.  Called if start() was called.
	def stop(self):
		pass

	# Optional dependency specification.
	# Returns a list of module specs.
	def get_dependencies(self):
		return []

	# Optional reconfiguration function.
	# Should accept the same arguments as the constructor.
	# Will be called on a running (started) module when Blankie wants
	# to stop and start a pair of modules with the same name
	# (differing only in parameters).
	# - If it returns True, the reconfiguration is considered to have
	#   been successful, and the module is now considered to be an
	#   instance corresponding to the new parameters.
	# - If it returns False, the old instance is stopped and a new
	#   instance is started instead.
	def reconfigure(self, *_args, **_kwargs):
		return False

	# Run a 'blankie module ...' command.
	# (Runs outside the daemon process.)
	def cli_command(self, *_args):
		raise NotImplementedError()

	# Handle a message received from the UNIX socket.
	def server_command(self, *_args):
		raise NotImplementedError()

	# Handle a packet received from the network bus.
	def bus_packet(self, packet):
		pass

# Module search path.  Populated in load_config.
module_dirs = []

# Currently running modules.
running_modules = []

# The modules we want to be running, according to the last invocation
# of update().  This is a global (instead of a local /
# start_stop_modules parameter) to support recursive calls to
# update().
wanted_modules = None

# Functions to call to build the list of modules which should be
# running right now.
# Functions are called in order of this associative array's keys.
# Functions accept one argument - a list, which they should mutate to
# describe which modules they want to be running right now.
selectors = {}

def load_module(module_name):
	for module_dir in module_dirs:
		module_file = module_dir  + '/' + module_name.replace('.', '/') + '.py'
		if os.path.exists(module_file):
			log.debug('Loading module %r from %r', module_name, module_file)
			python_module_name = 'blankie.modules.' + module_name

			# https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly
			spec = importlib.util.spec_from_file_location(python_module_name, module_file)
			module = importlib.util.module_from_spec(spec)
			sys.modules[python_module_name] = module
			spec.loader.exec_module(module)

			return

	raise blankie.UserError('Module %r not found (looked in: %r)' % (
		module_name,
		module_dirs,
	))

# Map from module specs to Module instances.
module_instances = {}

def get(module_spec):
	if module_spec in module_instances:
		return module_instances[module_spec]

	module_name = module_spec[0]
	def search(p):
		return ([p] if p.name == module_name else []) + sum((search(c) for c in p.__subclasses__()), start=[])
	module_classes = search(Module)
	if len(module_classes) == 0:
		log.debug('Auto-loading module %r', module_name)
		load_module(module_name)
		module_classes = search(Module)

	assert len(module_classes) > 0, 'No module class defined with name == %r' % (module_name,)
	module_class = module_classes[-1]  # Use the most recently defined class

	# Instantiate
	module = module_class(*module_spec[1:])
	module_instances[module_spec] = module
	return module

# Start or stop modules, synchronizing running_modules against
# wanted_modules.
# The contract this function fulfills is that when it returns,
# running_modules matches wanted_modules.
def start_stop_modules():
	log.trace('Running modules:%s', ''.join('\n- ' + str(m) for m in running_modules))
	log.trace('Wanted  modules:%s', ''.join('\n- ' + str(m) for m in wanted_modules))

	# Because modules may themselves start or stop other modules when
	# they are started or stopped, support re-entrancy by performing
	# one operation at a time, and looping until there is no work left
	# to be done.  Note that wanted_modules may change "under our
	# feet" in response to a module starting or stopping.

	errors = []

	# Use a local function to break out of deep loops.
	def do_one_module():
		# 1. Reconfigure modules which can be reconfigured.
		for wanted_module in wanted_modules:
			if wanted_module not in running_modules:
				for i, running_module in enumerate(running_modules):
					if wanted_module[0] == running_module[0] and \
					   running_module not in wanted_modules:
						module = get(running_module)
						result = module.reconfigure(*wanted_module[1:])
						if result:
							running_modules[i] = wanted_module
							del module_instances[running_module]
							module_instances[wanted_module] = module
							log.debug('Reconfigured module %r from %r to %r.',
								 wanted_module[0], running_module[1:], wanted_module[1:])
							return True  # Keep going

		# 2. Stop modules which we no longer want to be running.
		# Do this in reverse order of starting them.
		for i, running_module in reversed(list(enumerate(running_modules))):
			if running_module not in wanted_modules:
				del running_modules[i]
				log.debug('Stopping module %r', running_module)
				# It is important that, in case of an error, we revert
				# back to the original state insofar as possible.
				# This means that an error in one module should not cause
				# us to not try to stop other modules.
				module = get(running_module)
				try:
					module.stop()
				except Exception:
					log.error('Error when attempting to stop module %r:', str(running_module))
					traceback.print_exc()
					errors.append(running_module)
					return True
				log.debug('Stopped module %r', running_module)
				return True  # Keep going

		# 3. Start modules which we now want to be running.
		for wanted_module in wanted_modules:
			if wanted_module not in running_modules:
				running_modules.append(wanted_module)
				log.debug('Starting module: %r', wanted_module)
				get(wanted_module).start()
				log.debug('Started module: %r', wanted_module)
				# Put the module we just started at the end, so that
				# any dependents are stopped after it:
				if wanted_module in wanted_modules and wanted_module in running_modules:
					running_modules.remove(wanted_module)
					running_modules.append(wanted_module)
				return True  # Keep going

		# If we reached this point, there is no more work to do.
		return False

	while do_one_module():
		pass  # Keep going

	if errors:
		raise blankie.UserError('Failed to stop some modules.')

	log.debug('Modules are synchronized.')

# Start or stop modules according to the current circumstances.
def update():
	assert blankie.daemon.is_main_thread()

	# 1. Build the list of wanted modules.
	# Do this by calling the functions registered in selectors.

	log.debug('Updating list of modules to run with circumstances: %s', blankie.state)

	global wanted_modules
	wanted_modules = []

	for key in sorted(selectors.keys()):
		selector = selectors[key]
		log.trace('Calling module selector: %r', selector)
		selector(wanted_modules)

	# Add dependencies
	with_dependencies = []
	def add(module_spec):
		module = get(module_spec)
		for dependency in module.get_dependencies():
			add(dependency)
		with_dependencies.append(module_spec)
	for module_spec in wanted_modules:
		add(module_spec)
	wanted_modules = with_dependencies

	# Deduplicate
	wanted_modules = list(dict.fromkeys(wanted_modules))

	# 2. Start/stop modules accordingly.
	start_stop_modules()

def cli_command(module_spec_str, *args):
	# Synchronously instantiate a module and execute a module
	# subcommand, outside the daemon process.
	module_spec = shlex.split(module_spec_str)

	blankie.module.get(module_spec).cli_command(args)
