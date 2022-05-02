# xssmgr.modules.timer - built-in special module
# When active, sleeps until the next scheduled on_idle hook, and prods
# the main event loop to ensure on_idle hooks are activated
# accordingly.

import math
import subprocess
import threading

import xssmgr
import xssmgr.daemon
from xssmgr.util import *

class TimerModule(xssmgr.modules.Module):
	name = 'timer'

	def __init__(self, schedule):
		# Schedule of idle hooks (list of integers representing
		# seconds of idle time).
		self.timer_schedule = schedule

		# Timer instance, which waits until the next event
		self.timer = None

	def start(self):
		self.timer_start_next()

	def stop(self):
		self.timer_cancel()

	def timer_cancel(self):
		if self.timer is not None:
			logv('mod_timer: Canceling old timer wait task.')
			self.timer.cancel()
			self.timer = None

	def timer_start_next(self):
		self.timer_cancel()

		next_time = math.inf
		for timeout in self.timer_schedule:
			timeout_ms = timeout * 1000
			if xssmgr.state.idle_time < timeout_ms < next_time:
				next_time = timeout_ms

		if next_time < math.inf:
			to_sleep = next_time - xssmgr.state.idle_time + 1
			self.timer = threading.Timer(
				interval=to_sleep / 1000,
				function=xssmgr.daemon.call,
				args=(self.timer_handle_done,)
			)
			self.timer.start()
			logv('mod_timer: Started new timer for %d milliseconds.', to_sleep)

	def timer_handle_done(self):
		logv('mod_timer: Timer fired.')
		self.timer = None  # It exited cleanly, no need to cancel it.
		xssmgr.state.idle_time = int(subprocess.check_output(['xprintidle']))
		xssmgr.modules.update()

		self.timer_start_next()
