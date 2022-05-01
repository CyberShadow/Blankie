# xssmgr.modules.xss - built-in on_start module
# Manages an instance of a helper program, which receives screen saver
# events from the X server.  Used to know when the system becomes or
# stops being idle.

import subprocess
import threading
import types

import xssmgr
import xssmgr.daemon
from xssmgr.util import *

def mod_xss(*args):
	# Private state:
	s = xssmgr.global_state.setdefault(xssmgr.module_id, types.SimpleNamespace(

		# xss Popen object
		xss = None,

		# reader thread
		reader = None,

	))

	# Implementation:

	match args[0]:
		case 'start':
			# Start xss
			if s.xss is None:
				s.xss = subprocess.Popen(
					[xssmgr.lib_dir + '/xss'],
					stdout = subprocess.PIPE
				)

				if s.xss.stdout.readline() != b'init\n':
					logv('mod_xss: xss initialization failed.')
					s.xss.terminate()
					s.xss.communicate()
					s.xss = None
					raise Exception('mod_xss: Failed to start xss.')

				# Start event reader task
				s.reader = threading.Thread(target=xss_reader, args=(xssmgr.module_id, s.xss.stdout))
				s.reader.start()

				logv('mod_xss: Started xss (PID %d).', s.xss.pid)

		case 'stop':
			# Stop xss
			if s.xss is not None:
				logv('mod_xss: Killing xss (PID %d)...', s.xss.pid)
				s.xss.terminate()
				s.xss.communicate()
				s.xss = None

				s.reader.join()
				s.reader = None

				logv('mod_xss: Done.')

		case '_event':
			logv('mod_xss: Got line from xss: %s', str(args[1:]))
			match args[1]:
				case b'notify':
					(state, _kind, _forced) = args[2:5]
					if state == b'off':
						xssmgr.idle = 0
					else:
						xssmgr.idle = 1
					xssmgr.idle_time = int(subprocess.check_output(['xprintidle']))
					xssmgr.update_modules()

				case _:
					log('mod_xss: Unknown line received from xss: %s', str(args[1:]))


def xss_reader(module_id, f):
	while line := f.readline():
		xssmgr.daemon.call(xssmgr.module_command, module_id, '_event', *line.split())
	logv('mod_xss: xss exited (EOF).')
