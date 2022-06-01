# xssmgr.modules.physlock - optional on_lock module
# Disables TTY switching, to prevent switching to another (possibly
# unlocked) TTY while the lock screen is active.

import subprocess

import xssmgr

class PhysLockModule(xssmgr.module.Module):
	name = 'physlock'

	def start(self):
		subprocess.check_call(['physlock', '-l'])

	def stop(self):
		subprocess.check_call(['physlock', '-L'])
