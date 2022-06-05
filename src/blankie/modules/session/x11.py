# blankie.modules.session.x11 - X11 session module

import math
import os
import subprocess

import blankie

class X11Session(blankie.session.Session):
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

	# X server idle time (as provided by xprintidle), in seconds
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
			)) / 1000
		return self.idle_time

	def invalidate(self):
		self.idle_time = -1

	def __str__(self):
		return 'is idle: %s, idle time: %s' % (
			self.idle, self.idle_time
		)


def get_session():
	if 'DISPLAY' in os.environ:
		return (X11Session.name, os.environ['DISPLAY'])
	return None
