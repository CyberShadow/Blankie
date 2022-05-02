# xssmgr.daemon - Daemon event queue and lifecycle

import atexit
import contextlib
import os
import queue
import signal
import sys
import time

import xssmgr
import xssmgr.fifo
from xssmgr.util import *

# Daemon's PID file.
pid_file = xssmgr.run_dir + '/daemon.pid'

class EventLoop:
	queue = None

	stopping = False

	def __init__(self):
		self.queue = queue.Queue()

	def call(self, func, *args, **kwargs):
		'''Enqueue a function and call it from the main event loop.'''
		task = (func, args, kwargs)
		self.queue.put(task)

	def run(self):
		logv('Starting event loop.')
		while not self.stopping or not self.queue.empty():
			task = self.queue.get()
			(func, args, kwargs) = task
			logv('Calling %s with %s / %s', func, args, kwargs)
			func(*args, **kwargs)

_event_loop = EventLoop()
call = _event_loop.call

# Reload the configuration file and reconfigure.
def sighup(_signal, _frame):
	log('Got SIGHUP - asynchronously requesting reload.')
	# Make sure that the logic runs from the main loop, and not an
	# arbitrary place in the script.
	call(xssmgr.config.reload)


def shutdown_selector():
	xssmgr.wanted_modules.clear()


# Exit trap.
def shutdown():
	logv('Shutting down.')

	# Stop all modules.
	xssmgr.module_selectors['95-shutdown'] = shutdown_selector
	xssmgr.update_modules()

	# Delete PID file. We are exiting.
	with contextlib.suppress(FileNotFoundError):
		os.remove(pid_file)

	logv('Shutdown complete.')


# Daemon entry point.
def start():
	'''Starts the daemon in a fork.'''

	# Ensure a clean shut-down in any eventuality.
	atexit.register(shutdown)

	# Create an anonymous pipe used to signal startup success.
	(ready_r, ready_w) = os.pipe()
	(ready_r, ready_w) = (os.fdopen(ready_r, 'rb'), os.fdopen(ready_w, 'wb'))

	# Now, fork away the daemon main loop.
	daemon_pid = os.fork()
	if daemon_pid == 0:
		# Inside the forked process: set up and run the daemon.

		# Reload the configuration when receiving a SIGHUP.
		signal.signal(signal.SIGHUP, sighup)

		# Create PID file.
		with open(pid_file, 'w', encoding='ascii') as f:
			f.write(str(os.getpid()))

		# Start on-boot modules.
		xssmgr.config.reconfigure()

		# Signal readiness.
		ready_r.close()
		ready_w.write(b'ok')
		ready_w.close()

		# Run the event loop.
		_event_loop.run()

		# Event loop exited gracefully.
		logv('Daemon is exiting.')
		sys.exit(xssmgr.exit_code)

	# Clear our exit trap, as it should now run in the main loop subshell.
	atexit.unregister(shutdown)

	# Wait for the daemon to finish starting up.
	ready_w.close()
	if ready_r.read() == b'ok':
		log('Daemon started on %s (PID %d).',
			os.environ['DISPLAY'],
			daemon_pid)
	else:
		log('Daemon start-up failed.')
		os.waitpid(daemon_pid, 0)
		sys.exit(1)

def stop():
	log('Daemon is stopping...')
	# Python waits for daemon threads to exit before calling
	# atexit handlers. Because those threads are stopped in
	# response to cleanup performed in our atexit handler,
	# this deadlocks us.  Run the shutdown function manually
	# to avoid this.
	shutdown()
	atexit.unregister(shutdown)

	# Ask the daemon to stop, but continue pumping any extant events,
	# to allow worker threads to exit cleanly.
	_event_loop.stopping = True


def stop_remote():
	'''Connects to the daemon, tells it to stop, and waits for it to exit.'''
	if not os.path.exists(pid_file):
		log('PID file \'%s\' does not exist - daemon not running?', pid_file)
		sys.exit(2)

	with open(pid_file, 'rb') as f:
		daemon_pid = int(f.read())
	logv('Stopping daemon (PID %d)...', daemon_pid)
	xssmgr.fifo.notify('stop')
	while True:
		try:
			os.kill(daemon_pid, 0)
			time.sleep(0.1)  # Still running
		except ProcessLookupError:
			break
	log('Daemon stopped.')
