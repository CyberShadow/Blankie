# blankie.daemon - Daemon event queue and lifecycle

import atexit
import contextlib
import os
import queue
import signal
import sys
import threading
import time

import blankie
import blankie.server
from blankie.logging import log

# Daemon's PID file.
pid_file = blankie.run_dir + '/daemon.pid'

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
		log.debug('Starting event loop.')
		while not self.stopping or not self.queue.empty():
			task = self.queue.get()
			(func, args, kwargs) = task
			log.debug('Calling %r with %r / %r', func, args, kwargs)
			func(*args, **kwargs)

_event_loop = EventLoop()
call = _event_loop.call


# Thread that the event loop is running in.
# Used for assertions.
event_loop_thread = None

def is_main_thread():
	return threading.current_thread() is event_loop_thread


# Reload the configuration file and reconfigure.
def signal_stop(signalnum, _frame):
	log.info('Got signal %r - asynchronously requesting quit.', signal.strsignal(signalnum))
	# Make sure that the logic runs from the main loop, and not an
	# arbitrary place in the script.
	call(stop)

# Reload the configuration file and reconfigure.
def sighup(signalnum, _frame):
	log.info('Got signal %r - asynchronously requesting reload.', signal.strsignal(signalnum))
	# ditto
	call(blankie.config.reload)


def shutdown_selector(wanted_modules):
	wanted_modules.clear()


# Exit trap.
def shutdown():
	log.debug('Shutting down.')

	# Stop all modules.
	blankie.module.selectors['95-shutdown'] = shutdown_selector
	blankie.module.update()

	# Delete PID file. We are exiting.
	with contextlib.suppress(FileNotFoundError):
		os.remove(pid_file)

	log.debug('Shutdown complete.')


# Daemon entry point.
def start(fork=True):
	'''Starts the daemon in a fork.'''

	# Ensure a clean shut-down in any eventuality.
	atexit.register(shutdown)

	if fork:
		# Create an anonymous pipe used to signal startup success.
		(ready_r, ready_w) = os.pipe()
		(ready_r, ready_w) = (os.fdopen(ready_r, 'rb'), os.fdopen(ready_w, 'wb'))

		# Now, fork away the daemon main loop.
		daemon_pid = os.fork()
	else:
		daemon_pid = 0

	if daemon_pid == 0:
		# Inside the forked process: set up and run the daemon.

		# Stop gracefully when receiving a SIGINT/SIGTERM.
		signal.signal(signal.SIGINT, signal_stop)
		signal.signal(signal.SIGTERM, signal_stop)

		# Reload the configuration when receiving a SIGHUP.
		signal.signal(signal.SIGHUP, sighup)

		# Create PID file.
		with open(pid_file, 'w', encoding='ascii') as f:
			f.write(str(os.getpid()))

		# Save current thread as the main thread.
		global event_loop_thread
		assert event_loop_thread is None
		event_loop_thread = threading.current_thread()

		# Start on-boot modules.
		blankie.config.reconfigure()

		# Signal readiness.
		if fork:
			ready_r.close()
			ready_w.write(b'ok')
			ready_w.close()

		# Run the event loop.
		_event_loop.run()

		# Event loop exited gracefully.
		log.debug('Daemon is exiting.')

		# Ensure the fork does not continue into the parent's code.
		sys.exit(0)

	# Clear our exit trap, as it should now run in the main loop subshell.
	atexit.unregister(shutdown)

	# Wait for the daemon to finish starting up.
	ready_w.close()
	if ready_r.read() != b'ok':
		log.critical('Daemon start-up failed.')
		os.waitpid(daemon_pid, 0)
		return 1

	log.info('Daemon started (PID %d).', daemon_pid)
	return 0

def stop():
	log.info('Daemon is stopping...')
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
		log.critical('PID file %r does not exist - daemon not running?', pid_file)
		sys.exit(2)

	with open(pid_file, 'rb') as f:
		daemon_pid = int(f.read())
	log.debug('Stopping daemon (PID %d)...', daemon_pid)
	blankie.server.notify('stop')
	while True:
		try:
			os.kill(daemon_pid, 0)
			time.sleep(0.1)  # Still running
		except ProcessLookupError:
			break
	log.info('Daemon stopped.')
