# xssmgr.modules.vlock - optional on_lock module
# Manages a per-TTY vlock instance to lock a TTY.

import os
import signal
import subprocess
import threading
import time

import xssmgr
import xssmgr.daemon
import xssmgr.modules.session.tty

class VLockPerSessionModule(xssmgr.module.Module):
	name = 'internal-vlock-session'

	def __init__(self, session_spec):
		super().__init__()
		self.session = xssmgr.module.get(session_spec)

		# Private state:

		# Popen of the vlock process.
		self.vlock_process = None

		# Waiting thread
		self.vlock_thread = None

	def start(self):
		if self.vlock_process is None:
			# Start vlock.
			self.log.debug('Starting vlock...')
			self.vlock_process = subprocess.Popen(
				['vlock'],
				stdin=self.session.fd,
				stdout=self.session.fd,
				stderr=self.session.fd,
			)
			self.log.debug('Started vlock (PID %d).', self.vlock_process.pid)
			self.vlock_thread = threading.Thread(target=self.vlock_waiter,
												 args=(self.vlock_process,))
			self.vlock_thread.start()

	def stop(self):
		if self.vlock_process is not None:
			self.log.debug('Killing vlock (PID %d)...', self.vlock_process.pid)

			self.vlock_process.terminate()
			self.vlock_process.wait()
			self.vlock_process = None

			self.vlock_thread.join()
			self.vlock_thread = None

			self.log.debug('Done.')

	def vlock_waiter(self, vlock_process):
		vlock_process.wait()
		xssmgr.daemon.call(self.vlock_handle_exit, vlock_process.pid)

	def vlock_handle_exit(self, pid):
		if self.vlock_process is None:
			self.log.debug('Ignoring stale vlock exit notification (not expecting one at this time, got PID %r).',
						   pid)
		elif pid != self.vlock_process.pid:
			self.log.debug('Ignoring stale vlock exit notification (wanted PID %d, got PID %r).',
						   self.vlock_process.pid, pid)
		else:
			self.log.security('vlock exited, unlocking.')
			# Unset this first, so we don't attempt to kill a
			# nonexisting process when this module is stopped.
			self.vlock_process = None
			xssmgr.unlock()


class VLockModule(xssmgr.session.PerSessionModuleLauncher):
	name = 'vlock'
	per_session_name = VLockPerSessionModule.name
	session_type = xssmgr.modules.session.tty.TTYSession.name # 'session.tty'
