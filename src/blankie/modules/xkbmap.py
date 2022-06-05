# blankie.modules.xkbmap - optional on_lock module
# Configures the XKB map as requested when activating the lock screen,
# and restores previous settings when deactivating.

import os
import subprocess

import blankie
import blankie.config

class XKBMapPerSessionModule(blankie.module.Module):
	name = 'internal-xkbmap-session'

	def __init__(self, session_spec, *args):
		super().__init__()
		self.display = session_spec[1]

		# Parameters:

		# The keyboard configuration to use when locked.
		self.xkbmap_args = args

		# Private state:

		# The previous keyboard configuration.
		self.xkbmap_state = None

	def start(self):
		# Save the old state.
		o = subprocess.check_output(['setxkbmap', '-query'])
		o = o.splitlines()
		o = [line.split(b': ') for line in o]
		o = [(b'-' + line[0], line[1].strip()) for line in o]
		o = [arg for line in o for arg in line]
		self.xkbmap_state = o
		# Configure the locked state.
		subprocess.check_call(['setxkbmap', *self.xkbmap_args],
							  env=dict(os.environ, DISPLAY=self.display))

	def stop(self):
		# Restore the old state.
		subprocess.check_call(['setxkbmap', *self.xkbmap_state],
							  env=dict(os.environ, DISPLAY=self.display))


class XKBMapModule(blankie.session.PerSessionModuleLauncher):
	name = 'xkbmap'
	per_session_name = XKBMapPerSessionModule.name
	session_type = blankie.modules.session.x11.X11Session.name # 'session.x11'
