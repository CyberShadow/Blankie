# xssmgr.modules.upower - optional on_start module
# Manages a upower --monitor instance, which receives events from the
# UPower daemon.  Used to know when the system power status changes
# (e.g. AC power is connected or disconnected), which would require
# re-evaluating xssmgr's configuration.

import subprocess
import threading

import xssmgr
import xssmgr.config
import xssmgr.daemon
from xssmgr.util import *

class UPowerModule(xssmgr.Module):
	name = 'upower'

	def __init__(self):
		# Private state:

		# Popen of the managed upower process.
		self.upower = None

		# reader thread
		self.reader_thread = None

	# Implementation:

	def start(self):
		if self.upower is None:
			self.upower = subprocess.Popen(
				['upower', '--monitor'],
				stdout=subprocess.PIPE)
			self.reader_thread = threading.Thread(target=self.upower_reader, args=(self.upower.stdout))
			self.reader_thread.start()
			logv('mod_upower: Started upower (PID %d).', self.upower.pid)

	def stop(self):
		if self.upower is not None:
			logv('mod_upower: Killing upower (PID %d)...', self.upower.pid)

			self.upower.terminate()
			self.upower.wait()
			self.upower = None

			self.reader_thread.join()
			self.reader_thread = None

			logv('mod_upower: Done.')

	def upower_handle_ping(self):
		logv('mod_upower: Got a line from upower, reconfiguring.')
		xssmgr.config.reconfigure()

	def upower_reader(self, f):
		while f.readline():
			xssmgr.daemon.call(self.upower_handle_ping)
