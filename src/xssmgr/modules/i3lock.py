# xssmgr.modules.i3lock - optional on_lock module
# Manages an i3lock instance.

import os
import signal
import subprocess
import threading
import time

import xssmgr
import xssmgr.daemon

class I3LockModule(xssmgr.modules.Module):
	# Our goals:
	# - Start i3lock when this module is started.
	# - If i3lock fails to start (initialize), abort.
	# - Stop (kill) i3lock, if it is running, when this module is stopped.
	# - Exit the locked state, stopping other on_lock modules, when i3lock exits.

	name = 'i3lock'

	def __init__(self, *args):
		super().__init__()

		# Parameters:

		# Additional i3lock arguments.
		self.i3lock_args = args

		# Private state:

		# PID of the forked i3lock process.
		self.i3lock_inner_pid = None

		# reader thread
		self.i3lock_reader_thread = None

	def start(self):
		if self.i3lock_inner_pid is None:
			# Start i3lock.
			# We run i3lock without --nofork, and we want to know
			# the PID of the inner (forked) i3lock process, so for
			# that we also need to know the PID of the outer
			# process.
			self.log.debug('Starting i3lock...')
			outer = subprocess.Popen(['i3lock', *self.i3lock_args], stdout=subprocess.PIPE)

			# Wait for the outer process to exit.
			# This signals that i3lock initialized (hopefully successfully).
			outer.wait()
			if outer.returncode != 0:
				raise xssmgr.UserError('mod_i3lock: i3lock failed to start!')

			# Find the inner process.
			p = subprocess.check_output(['ps', '--ppid', str(outer.pid), '-C', 'i3lock', '-o', 'pid'])
			p = p.splitlines()[-1]
			self.i3lock_inner_pid = int(p.strip())
			try:
				os.kill(self.i3lock_inner_pid, 0)
			except ProcessLookupError:
				raise xssmgr.UserError('mod_i3lock: Failed to find the PID of the forked i3lock process.')

			# Create a thread waiting for EOF from the pipe, to know when i3lock exits.
			# (We use this method to avoid polling with e.g. `kill -0`.)
			self.i3lock_reader_thread = threading.Thread(target=self.i3lock_reader, args=(outer.stdout, self.i3lock_inner_pid,))
			self.i3lock_reader_thread.start()

			self.log.debug('Started i3lock (PID %d).', self.i3lock_inner_pid)

	def stop(self):
		if self.i3lock_inner_pid is not None:
			self.log.debug('Killing i3lock (PID %d)...', self.i3lock_inner_pid)

			try:
				os.kill(self.i3lock_inner_pid, signal.SIGTERM)
				while True:
					os.kill(self.i3lock_inner_pid, 0)  # Wait for exit
					self.log.debug('Waiting...')
					time.sleep(0.1)
			except ProcessLookupError:
				pass  # i3lock exited, continue

			self.i3lock_inner_pid = None

			self.i3lock_reader_thread.join()
			self.i3lock_reader_thread = None

			self.log.debug('Done.')

	def i3lock_reader(self, f, pid):
		f.read()
		# If we're here, f.read() reached EOF, which means that all write ends
		# of the pipe were closed, which means that i3lock exited.
		xssmgr.daemon.call(self.i3lock_handle_exit, pid)

	def i3lock_handle_exit(self, pid):
		if self.i3lock_inner_pid is None:
			self.log.debug('Ignoring stale i3lock exit notification (not expecting one at this time, got PID %r).',
				 pid)
		elif pid != self.i3lock_inner_pid:
			self.log.debug('Ignoring stale i3lock exit notification (wanted PID %d, got PID %r).',
				 self.i3lock_inner_pid, pid)
		else:
			self.log.security('i3lock exited, unlocking.')
			# Unset these first, so we don't attempt to kill a
			# nonexisting process when this module is stopped.
			self.i3lock_inner_pid = None
			xssmgr.unlock()
