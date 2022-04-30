# xssmgr.modules.xset - built-in on_start module
# Manages the X server's XScreenSaver extension settings.  Used to
# configure when xss receives notifications about the system becoming
# idle.

import subprocess

import xssmgr
import xssmgr.config
from xssmgr.util import *

def mod_xset(*args):
	match args[0]:
		case 'start':
			# We configure the X screen saver to "activate" at the
			# requested idle time of the first idle hook.  Beyond
			# that, the timer module will activate and sleep until the
			# next idle hook.
			min_timeout = xssmgr.max_time
			max_timeout = 0
			for (timeout, _module) in xssmgr.config.configurator.on_idle_modules:
				if timeout <= 0:
					log('mod_xset: Invalid idle time: %d, ignoring', timeout)
					continue
				min_timeout = min(min_timeout, timeout)
				max_timeout = max(max_timeout, timeout)
			logv('mod_xset: Configuring X screensaver for idle hooks in the %d .. %d range.',
				 min_timeout, max_timeout)
			if max_timeout > 0:
				subprocess.check_call(['xset', 's', str(min_timeout), '0'])
			else:
				subprocess.check_call(['xset', 's', 'off'])

		case 'stop':
			# Disable X screensaver.
			subprocess.check_call(['xset', 's', 'off'])
