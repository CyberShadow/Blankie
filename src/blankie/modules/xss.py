# blankie.modules.xss - built-in on_start module
# Manages an instance of a helper program, which receives screen saver
# events from the X server.  Used to know when the system becomes or
# stops being idle.

import os
import subprocess
import threading

import blankie
import blankie.daemon
import blankie.modules.session.x11

class XSSPerSessionModule(blankie.module.Module):
	name = 'internal-xss-session'

	def __init__(self, session_spec):
		super().__init__()
		self.display = session_spec[1]
		self.session = blankie.module.get(session_spec)

		# xss Popen object
		self.xss_process = None

		# reader thread
		self.xss_reader_thread = None

	# Implementation:

	def start(self):
		# Start xss
		if self.xss_process is None:
			self.xss_process = subprocess.Popen(
				[blankie.lib_dir + '/xss'],
				stdout = subprocess.PIPE,
				env=dict(os.environ, DISPLAY=self.display),
			)

			if self.xss_process.stdout.readline() != b'init\n':
				self.log.debug('xss initialization failed.')
				self.xss_process.terminate()
				self.xss_process.communicate()
				self.xss_process = None
				raise blankie.UserError('mod_xss: Failed to start xss.')

			# Start event reader task
			self.xss_reader_thread = threading.Thread(target=self.xss_reader, args=(self.xss_process.stdout,))
			self.xss_reader_thread.start()

			self.log.debug('Started xss (PID %d).', self.xss_process.pid)

	def stop(self):
		# Stop xss
		if self.xss_process is not None:
			self.log.debug('Killing xss (PID %d)...', self.xss_process.pid)
			self.xss_process.terminate()
			self.xss_process.communicate()
			self.xss_process = None

			self.xss_reader_thread.join()
			self.xss_reader_thread = None

			self.log.debug('Done.')

	def xss_reader(self, f):
		while line := f.readline():
			blankie.daemon.call(self.xss_handle_event, *line.split())
		self.log.debug('xss exited (EOF).')

	def xss_handle_event(self, *args):
		self.log.debug('Got line from xss: %r', args)
		match args[0]:
			case b'notify':
				(state, _kind, _forced) = args[1:4]
				if state == b'off':
					self.session.idle = False
				else:
					self.session.idle = True
				self.session.invalidate()
				blankie.module.update()

			case _:
				self.log.warning('Unknown line received from xss: %r', args)


class XSSModule(blankie.session.PerSessionModuleLauncher):
	name = 'xss'
	per_session_name = XSSPerSessionModule.name
	session_type = blankie.modules.session.x11.X11Session.name # 'session.x11'
