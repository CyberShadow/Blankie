# blankie.modules.physlock - optional on_lock module
# Manages a physlock instance to lock all VTs.

import subprocess
import threading

import blankie
import blankie.daemon
import blankie.modules.session.tty

class PhysLockModule(blankie.module.Module):
	name = 'physlock'

	def __init__(self, *args):
		super().__init__()

		# Parameters:

		# Additional physlock arguments.
		self.physlock_args = args

		# Private state:

		# Popen of the physlock process.
		self.physlock_process = None

		# Waiting thread
		self.physlock_thread = None

	def start(self):
		if self.physlock_process is None:
			# Start physlock.
			self.log.debug('Starting physlock...')
			self.physlock_process = subprocess.Popen(['physlock', *self.physlock_args])
			self.log.debug('Started physlock (PID %d).', self.physlock_process.pid)
			self.physlock_thread = threading.Thread(target=self.physlock_waiter,
													args=(self.physlock_process,))
			self.physlock_thread.start()

	def stop(self):
		if self.physlock_process is not None:
			self.log.debug('Killing physlock (PID %d)...', self.physlock_process.pid)

			self.physlock_process.terminate()
			self.physlock_process.wait()
			self.physlock_process = None

			self.physlock_thread.join()
			self.physlock_thread = None

			subprocess.check_call(['physlock', '-L'])

			# PhysLock picks a free TTY to show its password prompt, and switches it.
			# Unfortunately, its UX for handling a SIGTERM is poor, and it leaves that
			# TTY open without switching back or printing anything.
			# It would be nice if we could improve on that and either switch back to a
			# logged-in TTY or at least print a message that the system is now
			# unlocked, but unfortunately we can't do either without root access or
			# some kind of resident program that keeps a handle to a logged-in
			# session.

			self.log.debug('Done.')

	def physlock_waiter(self, physlock_process):
		physlock_process.wait()
		blankie.daemon.call(self.physlock_handle_exit, physlock_process.pid)

	def physlock_handle_exit(self, pid):
		if self.physlock_process is None:
			self.log.debug('Ignoring stale physlock exit notification (not expecting one at this time, got PID %r).',
						   pid)
		elif pid != self.physlock_process.pid:
			self.log.debug('Ignoring stale physlock exit notification (wanted PID %d, got PID %r).',
						   self.physlock_process.pid, pid)
		else:
			self.log.security('physlock exited, unlocking.')
			# Unset this first, so we don't attempt to kill a
			# nonexisting process when this module is stopped.
			self.physlock_process = None
			blankie.unlock()
