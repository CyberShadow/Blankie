# xssmgr.modules.xkbmap - optional on_lock module
# Configures the XKB map as requested when activating the lock screen,
# and restores previous settings when deactivating.

import subprocess
import types

import xssmgr
import xssmgr.config
import xssmgr.fifo
from xssmgr.util import *

def mod_xkbmap(*args):
	# Parameters:

	# The keyboard configuration to use when locked.
	xkbmap_args = xssmgr.module_args

	# Private state:
	s = xssmgr.global_state.setdefault(xssmgr.module_id, types.SimpleNamespace(

		# The previous keyboard configuration.
		xkbmap_state = None,

	))

	# Implementation:

	match args[1]:
		case 'start':
			# Save the old state.
			o = subprocess.check_output(['setxkbmap', '-query'])
			o = o.splitlines()
			o = [line.split(b': ') for line in o]
			o = [(b'-' + line[0], line[1].strip()) for line in o]
			o = [arg for line in o for arg in line]
			s.xkbmap_state = o
			# Configure the locked state.
			subprocess.check_call(['setxkbmap', *xkbmap_args])
		case 'stop':
			# Restore the old state.
			subprocess.check_call(['setxkbmap', *s.xkbmap_state])
