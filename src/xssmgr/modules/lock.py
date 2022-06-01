# xssmgr.modules.lock - built-in special module
# Changes the "locked" state.

import xssmgr

# Additionally define a lock module, which can be added to an on_idle
# hook to lock the screen when idle.
class LockModule(xssmgr.module.Module):
	name = 'lock'

	def start(self):
		self.log.debug('Locking (because the lock module is being enabled).')
		xssmgr.lock()

	def stop(self):
		self.log.debug('Unlocking (because the lock module is being disabled).')
		xssmgr.unlock()


# Ensure lock module isn't stopped upon locking
def lock_selector(wanted_modules):
	if xssmgr.state.locked:
		wanted_modules.append(('lock', ))
xssmgr.module.selectors['50-lock'] = lock_selector
