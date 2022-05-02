# xssmgr.modules.xbacklight - optional on_idle module
# Runs and manages an xbacklight process, which fades the screen to
# black over the configured duration.

import subprocess
import threading

import xssmgr
import xssmgr.daemon
from xssmgr.util import *

def _parse_config(args):
	xbacklight_args = []
	xbacklight_set_args = []

	i = 0
	while i < len(args):
		match args[i]:
			case '-ctrl' | '-display' | '-perceived':
				xbacklight_args += args[i : i+2]
				i += 2
			case _:
				xbacklight_set_args += [args[i]]
				i += 1

	return (xbacklight_args, xbacklight_set_args)

class XBacklightModule(xssmgr.Module):
	name = 'xbacklight'

	def __init__(self, *args):
		# Parameters:

		# Additional arguments, used for both querying and setting (such as
		# -ctrl or -perceived).
		self.xbacklight_args = None

		# Additional arguments for fading the brightness (such as -time,
		# -fps or -steps). Generally should have -time corresponding to
		# the time until the next/final idle event, and -steps or -fps.
		self.xbacklight_set_args = None

		(self.xbacklight_args, self.xbacklight_set_args) = _parse_config(args)

		# Private state:

		# Popen of any running xbacklight process.
		self.xbacklight = None

		# The original screen brightness.
		self.brightness = None

	def reconfigure(self, *args):
		(new_xbacklight_args, new_xbacklight_set_args) = _parse_config(args)
		# Can only reconfigure if non-set args are the same
		if self.xbacklight_args == new_xbacklight_args:
			self.xbacklight_set_args = new_xbacklight_set_args
			return True
		return False

	def start(self):
		if self.xbacklight is None:
			self.brightness = subprocess.check_output(['xbacklight', *self.xbacklight_args, '-getf']).rstrip(b'\n')
			logv('mod_xbacklight: Got original brightness (%s).', self.brightness)
			args = ['xbacklight', *self.xbacklight_args, '-set', '0', *self.xbacklight_set_args]
			logv('mod_xbacklight: Running: %s', str(args))
			self.xbacklight = subprocess.Popen(args, stdout=subprocess.PIPE)
			logv('mod_xbacklight: Started xbacklight (PID %d).', self.xbacklight.pid)
			threading.Thread(target=self.wait_exit, args=(self.xbacklight.stdout,)).start()

	def stop(self):
		if self.xbacklight is not None:
			logv('mod_xbacklight: Killing xbacklight (PID %d)...', self.xbacklight.pid)
			self.xbacklight.terminate()
			self.xbacklight.communicate()
			self.xbacklight = None
			logv('mod_xbacklight: Done.')

		if self.brightness is not None:
			logv('mod_xbacklight: Restoring original brightness (%s).', self.brightness)
			subprocess.call(['xbacklight', *self.xbacklight_args, '-set', self.brightness, '-steps', '1', '-time', '0'])
			self.brightness = None

	def wait_exit(self, f):
		# Get notified when it exits, so we can forget the PID
		# (so we later don't kill an innocent process due to
		# PID reuse).
		f.read() # Wait for EOF
		xssmgr.daemon.call(self._exited)

	def _exited(self):
		if self.xbacklight is not None:
			self.xbacklight.wait()
			logv('mod_xbacklight: xbacklight exited with status %d.', self.xbacklight.returncode)
			self.xbacklight = None
		else:
			logv('mod_xbacklight: Ignoring stale exit notification.')
