# xssmgr.modules.xset - built-in on_start module
# Manages the X server's XScreenSaver extension settings.  Used to
# configure when xss receives notifications about the system becoming
# idle.

import subprocess

import xssmgr
import xssmgr.config
from xssmgr.util import *

class XSetModule(xssmgr.modules.Module):
	name = 'xset'

	def __init__(self, time):
		# Idle time in seconds of the first idle hook.
		self.xset_time = time

	def reconfigure(self, time):
		self.xset_time = time
		logv('mod_xset: Reconfiguring X screensaver to activate after %s seconds.',
			 self.xset_time)
		subprocess.check_call(['xset', 's', str(self.xset_time), '0'])
		return True

	def start(self):
		# We configure the X screen saver to "activate" at the
		# requested idle time of the first idle hook.  Beyond that,
		# the timer module will activate and sleep until the next idle
		# hook.
		logv('mod_xset: Configuring X screensaver to activate after %s seconds.',
			 self.xset_time)
		subprocess.check_call(['xset', 's', str(self.xset_time), '0'])

	def stop(self):
		logv('mod_xset: Disabling X screensaver.')
		subprocess.check_call(['xset', 's', 'off'])
