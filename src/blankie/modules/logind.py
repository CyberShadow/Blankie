# blankie.modules.logind - systemd-logind integration
# Used to reliably lock the system when it goes to sleep.

import os

import dbus

import blankie

class LogindModule(blankie.module.Module):
	name = 'logind'

	DBUS_SPEC = ('dbus',)

	def get_dependencies(self):
		return [self.DBUS_SPEC]

	def __init__(self):
		super().__init__()
		self.dbus = blankie.module.get(self.DBUS_SPEC)
		self.inhibitor_lock = None

	def start(self):
		def setup():
			self.dbus.system_bus.add_signal_receiver(
				self.handle_sleep_signal,
				signal_name='PrepareForSleep',
				dbus_interface='org.freedesktop.login1.Manager',
				path='/org/freedesktop/login1',
			)
			self.inhibit()
		self.dbus.glib.run_sync(setup)

	def stop(self):
		def teardown():
			self.dbus.system_bus.remove_signal_receiver(
				self.handle_sleep_signal,
				signal_name='PrepareForSleep',
				dbus_interface='org.freedesktop.login1.Manager',
				path='/org/freedesktop/login1',
			)
			if self.inhibitor_lock is not None:
				self.uninhibit()
		self.dbus.glib.run_sync(teardown)

	# Runs in the GLib main loop thread:
	def inhibit(self):
		assert self.inhibitor_lock is None
		obj = self.dbus.system_bus.get_object(
			bus_name='org.freedesktop.login1',
			object_path='/org/freedesktop/login1',
		)
		unix_fd = obj.Inhibit(
			"sleep",
			"Blankie",
			"Lock the system before sleep",
			"delay",
			dbus_interface='org.freedesktop.login1.Manager',
		)
		self.inhibitor_lock = unix_fd.take()

	# Safe to run from either thread
	def uninhibit(self):
		assert self.inhibitor_lock is not None
		self.log.debug('Releasing inhibitor lock.')
		os.close(self.inhibitor_lock)
		self.inhibitor_lock = None

	# Runs in the GLib main loop thread:
	def handle_sleep_signal(self, start):
		self.log.debug('System is %s sleep' % ('entering' if start else 'exiting'))
		if start:
			blankie.daemon.call(self.handle_enter_sleep)
		else:
			if self.inhibitor_lock is None:
				self.inhibit()
			else:
				self.log.warning('System is exiting sleep but we are already holding an inhibitor lock?')
			blankie.daemon.call(self.handle_exit_sleep)

	# Runs in the main thread:
	def handle_enter_sleep(self):
		# Reconfigure the system appropriately
		blankie.state.sleeping = True
		blankie.module.update()
		# Release the inhibitor lock
		# This must be done only after the above
		if self.inhibitor_lock is not None:
			self.uninhibit()
		else:
			self.log.warning('System is going to sleep but we are not holding an inhibitor lock?')

	# Runs in the main thread:
	def handle_exit_sleep(self):
		# Reconfigure the system appropriately
		blankie.state.sleeping = False
		blankie.module.update()
