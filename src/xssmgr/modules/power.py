# xssmgr.modules.power - optional on_idle module
# Runs a power action on start.

import subprocess

import xssmgr
from xssmgr.util import *

class PowerModule(xssmgr.modules.Module):
	name = 'power'

	def __init__(self, action = 'suspend'):
		# The action to execute.  Should be one of suspend, hibernate,
		# hybrid-sleep, suspend-then-hibernate, or poweroff.
		self.power_action = action

	def start(self):
		if xssmgr.state.idle_time == xssmgr.max_time:
			# The system is already executing a power action.
			return
		subprocess.check_call(['systemctl', self.power_action])

	def stop(self):
		pass
