# xssmgr.modules.lock - built-in special module
# Changes the "locked" state.

import xssmgr
from xssmgr.util import *

# Additionally define a lock module, which can be added to an on_idle
# hook to lock the screen when idle.
def mod_lock(*args):
	match args[0]:
		case 'start':
			logv('mod_lock: Locking (because the lock module is being enabled).')
			xssmgr.lock()

		case 'stop':
			logv('mod_lock: Unlocking (because the lock module is being disabled).')
			xssmgr.unlock()


# Ensure lock module isn't stopped upon locking
def lock_selector():
	if xssmgr.locked:
		xssmgr.wanted_modules.append(('lock', ))
xssmgr.module_selectors['50-lock'] = lock_selector
