# blankie.modules.logind - systemd-logind integration
# Used to reliably lock the system when it goes to sleep.

import blankie

class LogindModule(blankie.module.Module):
	name = 'logind'

	DBUS_SPEC = ('dbus',)

	def get_dependencies(self):
		return [self.DBUS_SPEC]

	def __init__(self):
		super().__init__()
		self.dbus = blankie.module.get(self.DBUS_SPEC)

	def start(self):
		def setup():
			self.dbus.system_bus.add_signal_receiver(
				self.handle_sleep_signal,
				signal_name='PrepareForSleep',
				dbus_interface='org.freedesktop.login1.Manager',
				path='/org/freedesktop/login1',
			)
		self.dbus.glib.run_sync(setup)

	def stop(self):
		def teardown():
			self.dbus.system_bus.remove_signal_receiver(
				self.handle_sleep_signal,
				signal_name='PrepareForSleep',
				dbus_interface='org.freedesktop.login1.Manager',
				path='/org/freedesktop/login1',
			)
		self.dbus.glib.run_sync(teardown)

	# Runs in the GLib main loop thread:
	def handle_sleep_signal(self, start):
		self.log.debug('System is %s sleep' % ('entering' if start else 'exiting'))
		if not start:
			blankie.daemon.call(self.handle_exit_sleep)

	def handle_exit_sleep(self):
		pass  # TODO
