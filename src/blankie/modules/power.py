# blankie.modules.power - optional on_idle module
# Runs a power action on start.

import math
import subprocess

import blankie

class PowerModule(blankie.module.Module):
	name = 'power'

	def __init__(self, action = 'suspend'):
		super().__init__()

		# The action to execute.  Should be one of suspend, hibernate,
		# hybrid-sleep, suspend-then-hibernate, or poweroff.
		self.power_action = action

	def start(self):
		if blankie.get_idle_since() == -math.inf:
			# The system is already executing a power action.
			return
		subprocess.check_call(['systemctl', self.power_action])

	def stop(self):
		pass
