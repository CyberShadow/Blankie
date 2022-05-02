# xssmgr.modules.xset - built-in on_start module
# Manages the X server's XScreenSaver extension settings.  Used to
# configure when xss receives notifications about the system becoming
# idle.

import subprocess

import xssmgr
import xssmgr.config

class XSetModule(xssmgr.modules.Module):
	name = 'xset'

	def __init__(self, time):
		super().__init__()

		# Idle time in seconds of the first idle hook.
		self.xset_time = time

	def reconfigure(self, time):
		self.xset_time = time
		self.log.debug('Reconfiguring X screensaver to activate after %s seconds.',
			 self.xset_time)
		subprocess.check_call(['xset', 's', str(self.xset_time), '0'])
		return True

	def start(self):
		# We configure the X screen saver to "activate" at the
		# requested idle time of the first idle hook.  Beyond that,
		# the timer module will activate and sleep until the next idle
		# hook.
		self.log.debug('Configuring X screensaver to activate after %s seconds.',
			 self.xset_time)
		subprocess.check_call(['xset', 's', str(self.xset_time), '0'])

	def stop(self):
		self.log.debug('Disabling X screensaver.')
		subprocess.check_call(['xset', 's', 'off'])
