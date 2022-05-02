# xssmgr.modules.xss - built-in on_start module
# Manages an instance of a helper program, which receives screen saver
# events from the X server.  Used to know when the system becomes or
# stops being idle.

import subprocess
import threading

import xssmgr
import xssmgr.daemon
from xssmgr.util import *

class XSSModule(xssmgr.Module):
	name = 'xss'

	def __init__(self):
		# xss Popen object
		self.xss_process = None

		# reader thread
		self.xss_reader_thread = None

	# Implementation:

	def start(self):
		# Start xss
		if self.xss_process is None:
			self.xss_process = subprocess.Popen(
				[xssmgr.lib_dir + '/xss'],
				stdout = subprocess.PIPE
			)

			if self.xss_process.stdout.readline() != b'init\n':
				logv('mod_xss: xss initialization failed.')
				self.xss_process.terminate()
				self.xss_process.communicate()
				self.xss_process = None
				raise Exception('mod_xss: Failed to start xss.')

			# Start event reader task
			self.xss_reader_thread = threading.Thread(target=self.xss_reader, args=(self.xss_process.stdout,))
			self.xss_reader_thread.start()

			logv('mod_xss: Started xss (PID %d).', self.xss_process.pid)

	def stop(self):
		# Stop xss
		if self.xss_process is not None:
			logv('mod_xss: Killing xss (PID %d)...', self.xss_process.pid)
			self.xss_process.terminate()
			self.xss_process.communicate()
			self.xss_process = None

			self.xss_reader_thread.join()
			self.xss_reader_thread = None

			logv('mod_xss: Done.')

	def xss_reader(self, f):
		while line := f.readline():
			xssmgr.daemon.call(self.xss_handle_event, *line.split())
		logv('mod_xss: xss exited (EOF).')

	def xss_handle_event(self, *args):
		logv('mod_xss: Got line from xss: %s', str(args))
		match args[0]:
			case b'notify':
				(state, _kind, _forced) = args[1:4]
				if state == b'off':
					xssmgr.idle = 0
				else:
					xssmgr.idle = 1
				xssmgr.idle_time = int(subprocess.check_output(['xprintidle']))
				xssmgr.update_modules()

			case _:
				log('mod_xss: Unknown line received from xss: %s', str(args))
