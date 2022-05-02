# xssmgr.modules.xbacklight - optional on_idle module
# Runs and manages an xbacklight process, which fades the screen to
# black over the configured duration.

import subprocess
import threading

import xssmgr
import xssmgr.daemon
from xssmgr.logging import log

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

class XBacklightModule(xssmgr.modules.Module):
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
		self.xbacklight_process = None

		# The original screen brightness.
		self.xbacklight_brightness = None

	def reconfigure(self, *args):
		(new_xbacklight_args, new_xbacklight_set_args) = _parse_config(args)
		# Can only reconfigure if non-set args are the same
		if self.xbacklight_args == new_xbacklight_args:
			self.xbacklight_set_args = new_xbacklight_set_args
			return True
		return False

	def start(self):
		if self.xbacklight_process is None:
			self.xbacklight_brightness = subprocess.check_output(['xbacklight', *self.xbacklight_args, '-getf']).rstrip(b'\n')
			log.debug('mod_xbacklight: Got original brightness (%s).', self.xbacklight_brightness)
			args = ['xbacklight', *self.xbacklight_args, '-set', '0', *self.xbacklight_set_args]
			log.debug('mod_xbacklight: Running: %s', str(args))
			self.xbacklight_process = subprocess.Popen(args, stdout=subprocess.PIPE)
			log.debug('mod_xbacklight: Started xbacklight (PID %d).', self.xbacklight_process.pid)
			threading.Thread(target=self.xbacklight_reader, args=(self.xbacklight_process.stdout,)).start()

	def stop(self):
		if self.xbacklight_process is not None:
			log.debug('mod_xbacklight: Killing xbacklight (PID %d)...', self.xbacklight_process.pid)
			self.xbacklight_process.terminate()
			self.xbacklight_process.communicate()
			self.xbacklight_process = None
			log.debug('mod_xbacklight: Done.')

		if self.xbacklight_brightness is not None:
			log.debug('mod_xbacklight: Restoring original brightness (%s).', self.xbacklight_brightness)
			subprocess.call(['xbacklight', *self.xbacklight_args, '-set', self.xbacklight_brightness, '-steps', '1', '-time', '0'])
			self.xbacklight_brightness = None

	def xbacklight_reader(self, f):
		# Get notified when it exits, so we can forget the PID
		# (so we later don't kill an innocent process due to
		# PID reuse).
		f.read() # Wait for EOF
		xssmgr.daemon.call(self.xbacklight_handle_exit)

	def xbacklight_handle_exit(self):
		if self.xbacklight_process is not None:
			self.xbacklight_process.wait()
			log.debug('mod_xbacklight: xbacklight exited with status %d.', self.xbacklight_process.returncode)
			self.xbacklight_process = None
		else:
			log.debug('mod_xbacklight: Ignoring stale exit notification.')
