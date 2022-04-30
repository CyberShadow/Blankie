# xssmgr.modules.upower - optional on_start module
# Manages a upower --monitor instance, which receives events from the
# UPower daemon.  Used to know when the system power status changes
# (e.g. AC power is connected or disconnected), which would require
# re-evaluating xssmgr's configuration.

import subprocess
import threading
import types

import xssmgr
import xssmgr.config
import xssmgr.fifo
from xssmgr.util import *

def mod_upower(*args):
	# Private state:
	s = xssmgr.global_state.setdefault(xssmgr.module_id, types.SimpleNamespace(

		# Popen of the managed upower process.
		upower = None,

		# reader thread
		reader = None
	))

	# Implementation:

	match args[0]:
		case 'start':
			if s.upower is None:
				s.upower = subprocess.Popen(
					['upower', '--monitor'],
					stdout=subprocess.PIPE)
				s.reader = threading.Thread(target=upower_reader, args=(xssmgr.module_id, s.upower.stdout))
				s.reader.start()
				logv('mod_upower: Started upower (PID %d).', s.upower.pid)
		case 'stop':
			if s.upower is not None:
				logv('mod_upower: Killing upower (PID %d)...', s.upower.pid)

				s.upower.terminate()
				s.upower.wait()
				s.upower = None

				s.reader.join()
				s.reader = None

				logv('mod_upower: Done.')
		case '_ping':
			logv('mod_upower: Got a line from upower, reconfiguring.')
			xssmgr.config.reconfigure()

def upower_reader(module_id, f):
	while f.readline():
		xssmgr.fifo.notify('module', module_id, '_ping')
