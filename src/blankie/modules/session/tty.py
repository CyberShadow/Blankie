# blankie.modules.session.tty - Linux tty session module

import os
import pty
import time

import blankie

class TTYSession(blankie.session.Session):
	name = 'session.tty'

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

	def get_idle_since(self):
		return os.path.getmtime(self.tty)

	def __str__(self):
		return 'last modified: %s seconds ago' % (
			time.time() - self.get_idle_time()
		)


def get_session():
	try:
		tty = os.ttyname(pty.STDERR_FILENO)
		return (TTYSession.name, tty)
	except Exception:
		return None
