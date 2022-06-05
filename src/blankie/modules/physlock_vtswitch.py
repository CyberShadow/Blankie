# blankie.modules.physlock_vtswitch - optional on_lock module
# Disables TTY switching, to prevent switching to another (possibly
# unlocked) TTY while the lock screen is active.

import subprocess

import blankie

class PhyslockVTSwitchModule(blankie.module.Module):
	name = 'physlock_vtswitch'

	def start(self):
		subprocess.check_call(['physlock', '-l'])

	def stop(self):
		subprocess.check_call(['physlock', '-L'])
