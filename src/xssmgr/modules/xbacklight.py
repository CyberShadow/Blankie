# xssmgr.modules.xbacklight - optional on_idle module
# Runs and manages an xbacklight process, which fades the screen to
# black over the configured duration.

import hashlib
import subprocess
import threading
import types

import xssmgr
import xssmgr.fifo
from xssmgr.util import *

def mod_xbacklight(*args):
	# Parameters:

	# Additional arguments, used for both querying and setting (such as
	# -ctrl or -perceived).
	xbacklight_args = []

	# Additional arguments for fading the brightness (such as -time,
	# -fps or -steps). Generally should have -time corresponding to
	# the time until the next/final idle event, and -steps or -fps.
	xbacklight_set_args = []

	# Sort module arguments into the above.
	i = 0
	while i < len(xssmgr.module_args):
		match xssmgr.module_args[i]:
			case '-ctrl' | '-display' | '-perceived':
				xbacklight_args += xssmgr.module_args[i : i+2]
				i += 2
			case _:
				xbacklight_set_args += [xssmgr.module_args[i]]
				i += 1

	# Private state:
	s = xssmgr.global_state.setdefault(xssmgr.module_id, types.SimpleNamespace(

		# Popen of any running xbacklight process.
		xbacklight = None,

		# The original screen brightness.
		brightness = None,

	))

	# Implementation:

	match args[0]:
		case 'hash':
			# Don't stop+start this module (thus momentarily resetting
			# brightness) when e.g. the -time parameter changes.
			xssmgr.module_id = hashlib.sha1(bytes(str(xbacklight_args), 'utf-8')).hexdigest()

		case 'start':
			if s.xbacklight is None:
				s.brightness = subprocess.check_output(['xbacklight', *xbacklight_args, '-getf'])
				logv('mod_xbacklight: Got original brightness (%s).', s.brightness)
				args = ['xbacklight', *xbacklight_args, '-set', '0', *xbacklight_set_args]
				logv('mod_xbacklight: Running: %s', str(args))
				s.xbacklight = subprocess.Popen(args, stdout=subprocess.PIPE)
				logv('mod_xbacklight: Started xbacklight (PID %d).', s.xbacklight.pid)
				def wait_exit(module_id, f):
					# Get notified when it exits, so we can forget the PID
					# (so we later don't kill an innocent process due to
					# PID reuse).
					f.read() # Wait for EOF
					xssmgr.fifo.notify('module', module_id, '_exited')
				threading.Thread(target=wait_exit, args=(xssmgr.module_id, s.xbacklight.stdout)).start()

		case 'stop':
			if s.xbacklight is not None:
				logv('mod_xbacklight: Killing xbacklight (PID %d)...', s.xbacklight.pid)
				s.xbacklight.terminate()
				s.xbacklight.communicate()
				s.xbacklight = None
				logv('mod_xbacklight: Done.')

			if s.brightness is not None:
				logv('mod_xbacklight: Restoring original brightness (%s).', s.brightness)
				subprocess.call(['xbacklight', *xbacklight_args, '-set', s.brightness, '-steps', '1', '-time', '0'])
				s.brightness = None

		case '_exited':
			if s.xbacklight is not None:
				s.xbacklight.wait()
				logv('mod_xbacklight: xbacklight exited with status %d.', s.xbacklight.returncode)
				s.xbacklight = None
			else:
				logv('mod_xbacklight: Ignoring stale exit notification.')
