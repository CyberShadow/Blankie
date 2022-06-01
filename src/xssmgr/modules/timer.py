# xssmgr.modules.timer - built-in special module
# When active, sleeps until the next scheduled on_idle hook, and prods
# the main event loop to ensure on_idle hooks are activated
# accordingly.

import math
import threading

import xssmgr
import xssmgr.daemon

class TimerModule(xssmgr.module.Module):
	name = 'timer'

	def __init__(self, schedule):
		super().__init__()

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
			self.log.debug('Canceling old timer wait task.')
			self.timer.cancel()
			self.timer = None

	def timer_start_next(self):
		self.timer_cancel()

		idle_time = xssmgr.get_idle_time()
		if idle_time < 0:
			return  # wake-lock

		next_time = math.inf
		for timeout in self.timer_schedule:
			if idle_time < timeout < next_time:
				next_time = timeout

		if next_time < math.inf:
			to_sleep = next_time - idle_time + 1
			self.timer = threading.Timer(
				interval=to_sleep,
				function=xssmgr.daemon.call,
				args=(self.timer_handle_done,)
			)
			self.timer.start()
			self.log.debug('Started new timer for %s seconds.', to_sleep)

	def timer_handle_done(self):
		self.log.debug('Timer fired.')
		self.timer = None  # It exited cleanly, no need to cancel it.
		for session in xssmgr.session.get_sessions():
			session.invalidate()
		xssmgr.module.update()

		self.timer_start_next()
