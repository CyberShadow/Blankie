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
		self.xss = None

		# reader thread
		self.reader = None

	# Implementation:

	def start(self):
		# Start xss
		if self.xss is None:
			self.xss = subprocess.Popen(
				[xssmgr.lib_dir + '/xss'],
				stdout = subprocess.PIPE
			)

			if self.xss.stdout.readline() != b'init\n':
				logv('mod_xss: xss initialization failed.')
				self.xss.terminate()
				self.xss.communicate()
				self.xss = None
				raise Exception('mod_xss: Failed to start xss.')

			# Start event reader task
			self.reader = threading.Thread(target=self.xss_reader, args=(self.xss.stdout,))
			self.reader.start()

			logv('mod_xss: Started xss (PID %d).', self.xss.pid)

	def stop(self):
		# Stop xss
		if self.xss is not None:
			logv('mod_xss: Killing xss (PID %d)...', self.xss.pid)
			self.xss.terminate()
			self.xss.communicate()
			self.xss = None

			self.reader.join()
			self.reader = None

			logv('mod_xss: Done.')

	def _event(self, *args):
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

	def xss_reader(self, f):
		while line := f.readline():
			xssmgr.daemon.call(self._event, *line.split())
		logv('mod_xss: xss exited (EOF).')
