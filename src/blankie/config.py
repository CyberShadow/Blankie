# blankie.config - loads, evaluates, and manages the user's configuration

import importlib
import os
import sys

import blankie
import blankie.module
from blankie.logging import log

# The user config module.
module = None

class Configurator:
	def __init__(self):
		self.reset()

	def reset(self):
		# Modules registered in the configuration.
		self.modules = []
		self.idle_timers = []

	# Re-evaluate the configuration and update our state to match.
	def evaluate(self):
		log.debug('Reconfiguring.')

		# Reset settings before (re-)evaluating the user configuration.
		self.reset()

		if not module:
			log.warning('No configuration!')
			return

		# Evaluate the user-defined configuration function.
		module.config(self)

	# Return the list of on_idle events' trigger times (in seconds of
	# ongoing idle time), in increasing order.
	def get_schedule(self):
		s = set()
		for timeout in self.idle_timers:
			s.add(timeout)
		return sorted(s)

	def selector(self, wanted_modules):
		'''Module selector which applies the user's configuration.'''

		# Re-run the user configuration function
		self.evaluate()

		schedule = self.get_schedule()

		# Core modules:

		# Configure the X screensaver, so that we receive idle /
		# unidle events; wants to know the time of the first idle
		# event, so that we are notified of this via xss.
		if len(schedule) > 0:
			wanted_modules.append(('xset', schedule[0]))

		idle_time = blankie.get_idle_time()
		if idle_time >= 0 and len(schedule) > 0:
			# Wakes us up when it's time to run the next on_idle hook(s).
			wanted_modules.append(('timer', frozenset(schedule)))

		# User-configured modules:
		wanted_modules.extend(self.modules)

	def print_status(self, f):
		'''Used in 'blankie status' command.'''
		f.write(b'Configuration-requested modules:\n')
		f.write(b''.join(b'- %r\n' % (spec,) for spec in self.modules))

	# Public API follows:

	def run_module(self, module_name, *parameters):
		'''Called from the user's configuration to request the given module.'''
		self.modules.append((module_name, *parameters))

	def is_locked(self) -> bool:
		'''Called from the user's configuration to check if the system
		is currently locked.'''
		return blankie.state.locked

	def is_idle_for(self, idle_seconds) -> bool:
		'''Called from the user's configuration to check if the system
		is idle for at least this many seconds.'''
		if not isinstance(idle_seconds, int) or idle_seconds <= 0:
			raise blankie.UserError('Invalid idle time - must be a positive integer')
		idle_time = blankie.get_idle_time()
		if idle_seconds < idle_time:
			return True
		else:
			# The system has not yet been idle for the given duration,
			# so return False. However, since the behavior of the
			# configuration function will change once the system
			# becomes idle for the given duration, also make a note of
			# this so that we will call the configuration function
			# again once this call's return value will change.
			self.idle_timers.append(idle_seconds)
			return False


configurator = Configurator()
blankie.module.selectors['20-config'] = configurator.selector

# (Re-)Load the configuration file.
def load():
	global module

	config_dirs = os.getenv('XDG_CONFIG_DIRS', '/etc').split(':')
	config_dirs = [os.getenv('XDG_CONFIG_HOME', os.environ['HOME'] + '/.config')] + config_dirs
	config_files = [d + '/blankie/config.py' for d in config_dirs]

	blankie.module.module_dirs = (
		[d + '/blankie/modules' for d in config_dirs] +
		[os.path.dirname(__file__) + '/modules']
	)

	for config_file in config_files:
		if os.path.exists(config_file):
			log.debug('Loading configuration from %r.', config_file)

			# https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly
			module_name = 'blankie_user_config'
			spec = importlib.util.spec_from_file_location(module_name, config_file)
			module = importlib.util.module_from_spec(spec)
			sys.modules[module_name] = module
			spec.loader.exec_module(module)
			return

	log.warning('WARNING: No configuration file found.')
	log.warning('Please check installation or create %r.', config_files[0])

# Reload the configuration file and re-apply the configuration.
def reload():
	log.info('Reloading configuration.')
	load()
	blankie.module.update()

# Re-evaluate the configuration and update our state to match.
def reconfigure():
	blankie.module.update()
