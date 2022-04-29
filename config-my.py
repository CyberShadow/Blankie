# Sample xssmgr configuration file.

# The main duty of thes configuration file is to define a function,
# config, which configures xssmgr according to the current
# circumstances.

# This function is re-evaluated every time the context (power / lock
# screen status) changes, so we can use conditionals here to customize
# the behavior.

# All functionality in xssmgr is enabled by registering modules to
# xssmgr hooks.  xssmgr offers three kinds of hooks:
#
# - on_start - for modules which should run always, along with
#   xssmgr.  These generally provide events that xssmgr reacts to.
#
#   xssmgr automatically registers some built-in on_start modules to
#   provide core functionality, such as reacting to the system being
#   idle for some time.
#
# - on_idle - for modules which should run once the X session
#   has been idle for a certain amount of time.
#
#   Modules are registered to run at the indicated number of seconds
#   since the last input.  Can be used to activate the lock screen or
#   perform power actions after inactivity.
#
#   If the system is about to be incapacitated (suspended or
#   hibernated), xssmgr starts all on_idle hooks (as if the system has
#   been idle for an infinite amount of time).
#
# - on_lock - for modules which should run when the lock screen
#   activates (whether due to a configured idle timeout or explicit
#   user request).
#
#   Good for enabling additional security to further lock down the
#   machine until it is unlocked.  The lock screen program itself is
#   also registered here.

# Here is a very simple configuration, which uses just two modules.
# It locks the screen after 15 minutes with i3lock.

# def config():
#     on_idle(15 * 60, 'lock')
#     on_lock('i3lock')

# Below is a more elaborate configuration, which is close to the
# author's personal xssmgr configuration.

import socket
import pathlib

def config():
	# Let's define some helper variables first.
	# We want a much shorter delay if the lock screen is already active.

	if not locked:
		# Settings for when the lock screen is not active.

		# We can have different settings for different machines by
		# checking the hostname.
		hostname = socket.gethostname()
		if hostname.startswith('home.'):
			delay = 10 * 60     # A longer timeout on the desktop PC.
		else:
			delay = 5 * 60      # A shorter timeout on other machines (laptops).

		action = ('lock',)      # Lock screen after 5 or 10 minutes
		fade = 60               # Fade to black over 1 minute before locking the screen
	else:
		# Settings for when the lock screen is active.

		delay = 15              # Turn something off after 15 seconds

		bat_status = pathlib.Path('/sys/class/power_supply/BAT0/status')
		if bat_status.exists() and bat_status.read_text() == 'Discharging\n':
			# If running on battery, suspend the system.
			action = ('power', 'suspend')
		else:
			# Otherwise (AC power), just turn the screen(s) off.
			action = ('dpms',)

		fade = 5                # Fade to black over 5 seconds before turning off

	# Register our selected modules at their corresponding idle times.

	on_idle(delay - fade, 'xbacklight', '-time', str(fade * 1000), '-fps', '15')

	on_idle(delay, *action)

	# Register some on-lock modules, to do some more interesting things
	# when the screen is locked.  These will be started when the lock
	# screen starts, and will be stopped when the lock screen exits.

	# Prevent TTY switching.
	# No need to worry if you forgot to log out on a TTY before walking away.
	on_lock('physlock')

	# Pause dunst notifications.
	# Don't want your PMs to pop up on top of the lock screen.
	on_lock('dunst')

	# Stop udiskie.
	# Don't want to auto-mount any USB sticks while the screen is locked.
	on_lock('udiskie')

	# # Change the keyboard to US QWERTY before locking the screen.
	# # Avoid frustration due to your password not working when you were
	# # actually typing it in Cyrillic.
	# on_lock xkbmap -layout us
	on_lock('xkblayout')

	# Finally, add the lock screen itself.  It should be the last module
	# to run, to ensure that other security modules run before the lock
	# screen becomes visible, thus confirming that the machine is secure.
	on_lock('i3lock', '--show-failed-attempts', '--image', os.path.expanduser('~/data/images/wallpaper/blurred.png'))

# Custom on_lock xssmgr module: udiskie
# Stops udiskie, which in turn stops automounting.

def mod_udiskie(*args):
	match args[0]:
		case 'start':
			subprocess.check_call(['systemctl', '--user', 'stop', 'cs-x-udiskie@:0.service'])
		case 'stop':
			subprocess.check_call(['systemctl', '--user', 'start', 'cs-x-udiskie@:0.service'])

# Custom on_lock xssmgr module: xkblayout
# I use a custom script which replaces the entire XKB configuration,
# to avoid some programs still using QWERTY keys in their hotkey bindings.

def mod_xkblayout(*args):
	match args[0]:
		case 'start':
			subprocess.check_call([os.path.expanduser('~/libexec/xkblayout'), '1']) # US Dvorak
		case 'stop':
			pass  # I don't care about restoring it.
