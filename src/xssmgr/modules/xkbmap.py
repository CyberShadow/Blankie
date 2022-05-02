# xssmgr.modules.xkbmap - optional on_lock module
# Configures the XKB map as requested when activating the lock screen,
# and restores previous settings when deactivating.

import subprocess

import xssmgr
import xssmgr.config
import xssmgr.fifo
from xssmgr.logging import log

class XKBMapModule(xssmgr.modules.Module):
	name = 'xkbmap'

	def __init__(self, *args):
		# Parameters:

		# The keyboard configuration to use when locked.
		self.xkbmap_args = args

		# Private state:

		# The previous keyboard configuration.
		self.xkbmap_state = None

	def start(self):
		# Save the old state.
		o = subprocess.check_output(['setxkbmap', '-query'])
		o = o.splitlines()
		o = [line.split(b': ') for line in o]
		o = [(b'-' + line[0], line[1].strip()) for line in o]
		o = [arg for line in o for arg in line]
		self.xkbmap_state = o
		# Configure the locked state.
		subprocess.check_call(['setxkbmap', *self.xkbmap_args])

	def stop(self):
		# Restore the old state.
		subprocess.check_call(['setxkbmap', *self.xkbmap_state])
