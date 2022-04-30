# xssmgr.modules.dunst - optional on_lock module
# Pauses dunst notifications, preventing them from being displayed on
# top of the lock screen.

import subprocess

def mod_dunst(*args):
	match args[0]:
		case 'start':
			subprocess.check_call(['dunstctl', 'set-paused', 'true'])

		case 'stop':
			subprocess.check_call(['dunstctl', 'set-paused', 'false'])
