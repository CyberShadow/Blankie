# xssmgr.modules.session.x11 - X11 session module

import math
import os
import subprocess

import xssmgr

class X11Session(xssmgr.session.Session):
	name = 'session.x11'

	# X11 DISPLAY string.
	display = None

	# Whether we are currently idle (according to X / xss).
	# Because xss is affected by X screen-saver inhibitors,
	# this may be False even if xprintidle would produce a large number.
	#
	# More precisely, this is defined as follows: if this is False, we
	# are guaranteed to receive an event (which will make this
	# variable True) before the system actually becomes idle for
	# longer than our first on_idle hook.
	idle = False

	# X server idle time (as provided by xprintidle), in milliseconds
	idle_time = -1

	def __init__(self, display):
		super().__init__()
		self.display = display

	def get_idle_time(self):
		if not self.idle:
			return -math.inf
		if self.idle_time == -1:
			self.idle_time = int(subprocess.check_output(
				['xprintidle'],
				env=dict(os.environ, DISPLAY=self.display)
			))
		return self.idle_time

	def invalidate(self):
		self.idle_time = -1

	def __str__(self):
		return 'is idle: %s, idle time: %s' % (
			self.idle, self.idle_time
		)
