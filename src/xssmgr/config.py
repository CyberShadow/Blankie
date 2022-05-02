# xssmgr.config - loads, evaluates, and manages the user's configuration

import importlib
import os

import xssmgr
from xssmgr.util import *

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
		self.on_idle_modules.append((idle_seconds, (module, *parameters)))

	def selector(self):
		'''Module selector which applies the user's configuration.'''
		xssmgr.wanted_modules.extend(self.on_start_modules)

		for (timeout, module) in self.on_idle_modules:
			if xssmgr.idle_time >= timeout * 1000:
				xssmgr.wanted_modules.append(module)

		# React to locking/unlocking by starting/stopping on_lock modules.
		if xssmgr.locked:
			xssmgr.wanted_modules.extend(self.on_lock_modules)

configurator = Configurator()
xssmgr.module_selectors['20-config'] = configurator.selector

# (Re-)Load the configuration file.
def load():
	global module

	config_dirs = os.getenv('XDG_CONFIG_DIRS', '/etc').split(':')
	config_dirs = [os.getenv('XDG_CONFIG_HOME', os.environ['HOME'] + '/.config')] + config_dirs
	config_files = [d + '/xssmgr/config.py' for d in config_dirs]

	xssmgr.module_dirs = (
		[d + '/xssmgr/modules' for d in config_dirs] +
		[os.path.dirname(__file__) + '/modules']
	)

	for config_file in config_files:
		if os.path.exists(config_file):
			logv('Loading configuration from \'%s\'.', config_file)

			# https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly
			module_name = 'xssmgr_user_config'
			spec = importlib.util.spec_from_file_location(module_name, config_file)
			module = importlib.util.module_from_spec(spec)
			sys.modules[module_name] = module
			spec.loader.exec_module(module)
			return

	log('WARNING: No configuration file found.')
	log('Please check installation or create \'%s\'.', config_files[0])

# Re-evaluate the configuration and update our state to match.
def reconfigure():
	logv('Reconfiguring.')

	# Reset settings before (re-)loading configuration file.
	configurator.reset()

	# Evaluate the user-defined configuration function.
	module.config(configurator)

	# Update our state to match.
	xssmgr.update_modules()

# Reload the configuration file and re-apply the configuration.
def reload():
	log('Reloading configuration.')
	load()
	reconfigure()