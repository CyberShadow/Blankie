# xssmgr.modules.dpms - optional on_idle module
# Turns off the screen(s) via the xset dpms command.

import subprocess

import xssmgr

def mod_dpms(*args):
	# Parameters:

	# The DPMS state to set.  User configurable.
	# Can be one of standby, suspend, or off.
	# For most modern computer screens, the effect will be the same.
	dpms_state = xssmgr.module_args[0] if len(xssmgr.module_args) > 0 else 'off'

	# Implementation:

	match args[0]:
		case 'start':
			subprocess.check_call(['xset', 'dpms', 'force', dpms_state])
		case 'stop':
			subprocess.check_call(['xset', 'dpms', 'force', 'on'])
			subprocess.check_call(['xset', '-dpms'])  # Disable default settings - we control DPMS
