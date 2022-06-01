# xssmgr.modules.session.console - Linux console session module

import os
import pty
import time

import xssmgr

class ConsoleSession(xssmgr.session.Session):
	name = 'session.console'

	# Path to the TTY device.
	tty = None

	# File descriptor for the TTY.
	fd = None

	def __init__(self, tty):
		super().__init__()
		self.tty = tty

	def start(self):
		self.fd = os.open(self.tty, os.O_RDWR | os.O_NOCTTY)
		super().start()

	def stop(self):
		super().stop()
		if self.fd is not None:
			os.close(self.fd)
			self.fd = None

	def get_idle_time(self):
		now = time.time()
		tty_time = os.path.getmtime(self.tty)
		return now - tty_time

	def __str__(self):
		return 'last modified: %s seconds ago' % (
			self.get_idle_time()
		)


def get_session():
	try:
		tty = os.ttyname(pty.STDERR_FILENO)
		return (ConsoleSession.name, tty)
	except Exception:
		return None
