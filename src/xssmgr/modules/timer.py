# xssmgr.modules.timer - built-in special module
# When active, sleeps until the next scheduled on_idle hook, and prods
# the main event loop to ensure on_idle hooks are activated
# accordingly.

import subprocess
import threading
import types

import xssmgr
import xssmgr.config
import xssmgr.daemon
from xssmgr.util import *

def mod_timer(*args):
	# Private state:
	s = xssmgr.global_state.setdefault(xssmgr.module_spec, types.SimpleNamespace(

		# Timer instance, which waits until the next event
		timer = None,

	))

	# Implementation:

	match args[0]:
		case 'start':
			timer_schedule(s)
		case 'stop':
			timer_cancel(s)
		case '_wait_done':
			logv('mod_timer: Timer fired.')
			s.timer = None  # It exited cleanly, no need to cancel it.
			xssmgr.idle_time = int(subprocess.check_output(['xprintidle']))
			xssmgr.update_modules()

			timer_schedule(s)

def timer_cancel(s):
	if s.timer is not None:
		logv('mod_timer: Canceling old timer wait task.')
		s.timer.cancel()
		s.timer = None

def timer_schedule(s):
	timer_cancel(s)

	next_time = xssmgr.max_time
	for (timeout, _module) in xssmgr.config.configurator.on_idle_modules:
		timeout_ms = timeout * 1000
		if xssmgr.idle_time < timeout_ms < next_time:
			next_time = timeout_ms

	if next_time < xssmgr.max_time:
		to_sleep = next_time - xssmgr.idle_time + 1
		s.timer = threading.Timer(
			interval=to_sleep / 1000,
			function=xssmgr.daemon.call,
			args=(xssmgr.module_command, xssmgr.module_spec, '_wait_done')
		)
		s.timer.start()
		logv('mod_timer: Started new timer for %d milliseconds.', to_sleep)
