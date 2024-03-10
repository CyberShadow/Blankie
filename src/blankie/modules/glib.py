# blankie.modules.glib - GLib main loop
# Runs a GLib MainLoop in a thread.
# Used for the D-Bus integration.

import threading

from gi.repository import GLib

import blankie

class GLibModule(blankie.module.Module):
	name = 'glib'

	def __init__(self):
		super().__init__()
		self.mainloop = None
		self.glib_thread = None

	def start(self):
		self.mainloop = GLib.MainLoop()
		self.glib_thread = threading.Thread(target=self.glib_thread_func)
		self.glib_thread.start()

	def stop(self):
		self.run_async(self.mainloop.quit)
		self.glib_thread.join()
		self.mainloop = None
		self.glib_thread = None

	# Run a function on the GLib main loop thread.
	# The function is run asynchronously, discarding the return value.
	def run_async(self, func):
		# Note: this works (without an explicit reference to the main
		# loop) because the main loop is attached to the default GLib
		# context.  This is OK for us because there will be at most
		# one instance of this module in a Blankie instance.
		# Details: https://docs.gtk.org/glib/func.idle_add.html
		GLib.idle_add(func)

	# Run a function on the GLib main loop thread.
	# The function is run synchronously, propagating any return value or exception.
	def run_sync(self, func):
		event = threading.Event()
		result_getter = []
		def run():
			try:
				value = func()
				result_getter.append(lambda: value)
			except Exception as e:
				# Re-throw in main thread
				def make_raiser(ex):
					# Double-nested closure to avoid "NameError: free
					# variable 'e' referenced before assignment in
					# enclosing scope"
					def raiser():
						raise ex
					return raiser
				result_getter.append(make_raiser(e))
			event.set()

		GLib.idle_add(run)
		event.wait()
		assert len(result_getter) == 1
		return result_getter[0]()

	def glib_thread_func(self):
		self.mainloop.run()
