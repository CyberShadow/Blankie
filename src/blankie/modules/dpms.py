# blankie.modules.dpms - optional on_idle module
# Turns off the screen(s) via the xset dpms command.

import os
import subprocess

import blankie

class DPMSPerSessionModule(blankie.module.Module):
	name = 'internal-dpms-session'

	def __init__(self, session_spec, dpms_state = 'off'):
		super().__init__()
		self.display = session_spec[1]

		# The DPMS state to set.  User configurable.
		# Can be one of standby, suspend, or off.
		# For most modern computer screens, the effect will be the same.
		self.dpms_state = dpms_state

	def start(self):
		subprocess.check_call(['xset', 'dpms', 'force', self.dpms_state],
							  env=dict(os.environ, DISPLAY=self.display))

	def stop(self):
		subprocess.check_call(['xset', 'dpms', 'force', 'on'],
							  env=dict(os.environ, DISPLAY=self.display))
		subprocess.check_call(['xset', '-dpms'],  # Disable default settings - we control DPMS
							  env=dict(os.environ, DISPLAY=self.display))


class DPMSModule(blankie.session.PerSessionModuleLauncher):
	name = 'dpms'
	per_session_name = DPMSPerSessionModule.name
	session_type = blankie.modules.session.x11.X11Session.name # 'session.x11'
