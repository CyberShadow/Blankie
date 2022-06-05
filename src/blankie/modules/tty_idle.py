# blankie.modules.tty_idle - built-in on_start module
# Monitors the timestamps of TTY devices, so that Blankie can be
# notified when a TTY stops being idle.

import threading

import inotify_simple

import blankie
import blankie.daemon
import blankie.modules.session.tty

class TTYIdlePerSessionModule(blankie.module.Module):
	name = 'internal-tty_idle-session'

	def __init__(self, session_spec):
		super().__init__()
		self.tty = session_spec[1]
		self.session = blankie.module.get(session_spec)

		# inotify object and watch descriptor
		self.inotify = inotify_simple.INotify()
		self.inotify_wd = None

		# Reader thread
		self.tty_thread = None

	# Implementation:

	def start(self):
		flags = (
			inotify_simple.flags.MODIFY |
			inotify_simple.flags.DELETE_SELF
		)
		self.inotify_wd = self.inotify.add_watch(self.tty, flags)

		# Start thread
		self.tty_thread = INotifyThread()
		self.tty_thread.module = self
		self.tty_thread.start()

	def stop(self):
		if self.tty_thread is not None:
			self.tty_thread.stop = True
			# This will generate an event, which will cause the thread
			# to exit.
			self.inotify.rm_watch(self.inotify_wd)

			self.tty_thread.join()
			self.tty_thread = None

			self.log.debug('Done.')

	def tty_idle_handle_event(self, thread):
		if thread is not self.tty_thread:
			self.log.debug('Ignoring stale TTY inotify event')
			return
		self.session.invalidate()
		blankie.module.update()


class INotifyThread(threading.Thread):
	stop = False
	module = None

	def run(self):
		for _ in self.module.inotify.read():
			if self.stop:
				return
			blankie.daemon.call(self.module.tty_idle_handle_event, self)


class TTYIdleModule(blankie.session.PerSessionModuleLauncher):
	name = 'tty_idle'
	per_session_name = TTYIdlePerSessionModule.name
	session_type = blankie.modules.session.tty.TTYSession.name # 'session.tty'
