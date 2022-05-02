# xssmgr.config - loads, evaluates, and manages the user's configuration

import importlib
import os
import sys

import xssmgr
import xssmgr.modules
from xssmgr.logging import log

# The user config module.
module = None

class Configurator:
	def __init__(self):
		self.reset()

	def reset(self):
		# Modules registered in the configuration.
		self.on_start_modules = []
		self.on_lock_modules = []
		self.on_idle_modules = []

	def on_start(self, module, *parameters):
		'''Called from the user's configuration to register an on-start module.'''
		self.on_start_modules.append((module, *parameters))

	def on_lock(self, module, *parameters):
		'''Called from the user's configuration to register an on-lock module.'''
		self.on_lock_modules.append((module, *parameters))

	def on_idle(self, idle_seconds, module, *parameters):
		'''Called from the user's configuration to register an on-idle module.'''
		if not isinstance(idle_seconds, int) or idle_seconds <= 0:
			raise Exception('Invalid idle time - must be a positive integer')
		self.on_idle_modules.append((idle_seconds, (module, *parameters)))

	def selector(self, wanted_modules):
		'''Module selector which applies the user's configuration.'''

		schedule = get_schedule()

		# Core modules:

		# Configure the X screensaver, so that we receive idle /
		# unidle events; wants to know the time of the first idle
		# event, so that we are notified of this via xss.
		if len(schedule) > 0:
			wanted_modules.append(('xset', schedule[0]))

		# React to locking/unlocking by starting/stopping on_lock modules.
		if xssmgr.state.locked:
			wanted_modules.extend(self.on_lock_modules)

		if xssmgr.state.idle and len(schedule) > 0:
			# Wakes us up when it's time to run the next on_idle hook(s).
			wanted_modules.append(('timer', frozenset(schedule)))

		# User-configured modules:

		wanted_modules.extend(self.on_start_modules)

		for (timeout, module_spec) in self.on_idle_modules:
			if xssmgr.state.idle_time >= timeout * 1000:
				wanted_modules.append(module_spec)

	def print_status(self, f):
		'''Used in 'xssmgr status' command.'''
		f.write('Configured on_start modules:\n')
		f.write(''.join('- %s\n' % (spec,) for spec in self.on_start_modules))
		f.write('Configured on_idle modules:\n')
		f.write(''.join('- %d %s\n' % line for line in self.on_idle_modules))
		f.write('Configured on_lock modules:\n')
		f.write(''.join('- %s\n' % (spec,) for spec in self.on_lock_modules))

configurator = Configurator()
xssmgr.modules.selectors['20-config'] = configurator.selector

# (Re-)Load the configuration file.
def load():
	global module

	config_dirs = os.getenv('XDG_CONFIG_DIRS', '/etc').split(':')
	config_dirs = [os.getenv('XDG_CONFIG_HOME', os.environ['HOME'] + '/.config')] + config_dirs
	config_files = [d + '/xssmgr/config.py' for d in config_dirs]

	xssmgr.modules.module_dirs = (
		[d + '/xssmgr/modules' for d in config_dirs] +
		[os.path.dirname(__file__) + '/modules']
	)

	for config_file in config_files:
		if os.path.exists(config_file):
			log.debug('Loading configuration from \'%s\'.', config_file)

			# https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly
			module_name = 'xssmgr_user_config'
			spec = importlib.util.spec_from_file_location(module_name, config_file)
			module = importlib.util.module_from_spec(spec)
			sys.modules[module_name] = module
			spec.loader.exec_module(module)
			return

	log.warning('WARNING: No configuration file found.')
	log.warning('Please check installation or create \'%s\'.', config_files[0])

# Re-evaluate the configuration and update our state to match.
def reconfigure():
	log.debug('Reconfiguring.')

	# Reset settings before (re-)loading configuration file.
	configurator.reset()

	# Evaluate the user-defined configuration function.
	module.config(configurator)

	# Update our state to match.
	xssmgr.modules.update()

# Reload the configuration file and re-apply the configuration.
def reload():
	log.info('Reloading configuration.')
	load()
	reconfigure()

# Return the list of on_idle events' trigger times (in seconds of
# ongoing idle time), in increasing order.
def get_schedule():
	s = set()
	for (timeout, _module_spec) in configurator.on_idle_modules:
		s.add(timeout)
	return sorted(s)
