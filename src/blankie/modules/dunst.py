# blankie.modules.dunst - optional on_lock module
# Pauses dunst notifications, preventing them from being displayed on
# top of the lock screen.

import subprocess

import blankie

class DunstModule(blankie.module.Module):
	name = 'dunst'

	def start(self):
		subprocess.check_call(['dunstctl', 'set-paused', 'true'])

	def stop(self):
		subprocess.check_call(['dunstctl', 'set-paused', 'false'])
