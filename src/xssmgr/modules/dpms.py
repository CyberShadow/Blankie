# xssmgr.modules.dpms - optional on_idle module
# Turns off the screen(s) via the xset dpms command.

import subprocess

import xssmgr

class DPMSModule(xssmgr.Module):
	name = 'dpms'

	def __init__(self, dpms_state = 'off'):
		# The DPMS state to set.  User configurable.
		# Can be one of standby, suspend, or off.
		# For most modern computer screens, the effect will be the same.
		self.dpms_state = dpms_state

	def start(self):
		subprocess.check_call(['xset', 'dpms', 'force', self.dpms_state])

	def stop(self):
		subprocess.check_call(['xset', 'dpms', 'force', 'on'])
		subprocess.check_call(['xset', '-dpms'])  # Disable default settings - we control DPMS
