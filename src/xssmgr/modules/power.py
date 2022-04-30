# xssmgr.modules.power - optional on_idle module
# Runs a power action on start.

import subprocess

import xssmgr
from xssmgr.util import *

def mod_power(*args):
	# Parameters:

	# The action to execute.  Should be one of suspend, hibernate,
	# hybrid-sleep, suspend-then-hibernate, or poweroff.
	power_action = xssmgr.module_args[0] if len(xssmgr.module_args) > 0 else 'suspend'

	# Implementation:

	match args[0]:
		case 'start':
			if xssmgr.idle_time == xssmgr.max_time:
				# The system is already executing a power action.
				return
			subprocess.check_call(['systemctl', power_action])
		case 'stop':
			pass
