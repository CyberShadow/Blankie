# xssmgr.modules.physlock - optional on_lock module
# Disables TTY switching, to prevent switching to another (possibly
# unlocked) TTY while the lock screen is active.

import subprocess

def mod_physlock(*args):
	match args[0]:
		case 'start':
			subprocess.check_call(['physlock', '-l'])

		case 'stop':
			subprocess.check_call(['physlock', '-L'])
