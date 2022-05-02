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

	def start(self):
		# We configure the X screen saver to "activate" at the
		# requested idle time of the first idle hook.  Beyond
		# that, the timer module will activate and sleep until the
		# next idle hook.
		schedule = xssmgr.config.get_schedule()
		if len(schedule) > 0:
			logv('mod_xset: Configuring X screensaver for idle hooks in the %s .. %s range.',
				 schedule[0], schedule[-1])
			subprocess.check_call(['xset', 's', str(schedule[0]), '0'])
		else:
			logv('mod_xset: No idle events configured, disabling X screensaver.')
			subprocess.check_call(['xset', 's', 'off'])

	def stop(self):
		# Disable X screensaver.
		subprocess.check_call(['xset', 's', 'off'])
