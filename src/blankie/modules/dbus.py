# blankie.modules.dbus - D-Bus interop and main loop

import dbus
from dbus.mainloop.glib import DBusGMainLoop

import blankie

class DBusModule(blankie.module.Module):
	name = 'dbus'

	GLIB_SPEC = ('glib',)

	def __init__(self):
		super().__init__()

		self.glib = blankie.module.get(self.GLIB_SPEC)
		self.dbus_mainloop = None
		self.system_bus = None

	def get_dependencies(self):
		return [self.GLIB_SPEC]

	def start(self):
		self.dbus_mainloop = DBusGMainLoop()
		self.system_bus = dbus.SystemBus(mainloop=self.dbus_mainloop)

	def stop(self):
		self.system_bus.close()
		self.system_bus = None
		self.dbus_mainloop = None
