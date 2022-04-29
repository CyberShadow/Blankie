# External on_lock xssmgr module: dunst
# Pauses dunst notifications, preventing them from being displayed on
# top of the lock screen.

def mod_dunst(*args):
	match args[0]:
		case 'start':
			subprocess.check_call(['dunstctl', 'set-paused', 'true'])

		case 'stop':
			subprocess.check_call(['dunstctl', 'set-paused', 'false'])
