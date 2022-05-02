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

class UPowerModule(xssmgr.modules.Module):
	name = 'upower'

	def __init__(self):
		super().__init__()

		# Private state:

		# Popen of the managed upower process.
		self.upower_process = None

		# reader thread
		self.upower_reader_thread = None

	# Implementation:

	def start(self):
		if self.upower_process is None:
			self.upower_process = subprocess.Popen(
				['upower', '--monitor'],
				stdout=subprocess.PIPE)
			self.upower_reader_thread = threading.Thread(target=self.upower_reader, args=(self.upower_process.stdout))
			self.upower_reader_thread.start()
			self.log.debug('Started upower (PID %d).', self.upower_process.pid)

	def stop(self):
		if self.upower_process is not None:
			self.log.debug('Killing upower (PID %d)...', self.upower_process.pid)

			self.upower_process.terminate()
			self.upower_process.wait()
			self.upower_process = None

			self.upower_reader_thread.join()
			self.upower_reader_thread = None

			self.log.debug('Done.')

	def upower_reader(self, f):
		while f.readline():
			xssmgr.daemon.call(self.upower_handle_ping)

	def upower_handle_ping(self):
		self.log.debug('Got a line from upower, reconfiguring.')
		xssmgr.config.reconfigure()
