# Sample xssmgr configuration file.

# The main duty of thes configuration file is to define a function,
# xssmgr_config, which configures xssmgr according to the current
# circumstances.

# This function is re-evaluated every time the context (power / lock
# screen status) changes, so we can use conditionals here to customize
# the behavior.

# All functionality in xssmgr is enabled by registering modules to
# xssmgr hooks.  xssmgr offers three kinds of hooks:
#
# - xssmgr_on_start - for modules which should run always, along with
#   xssmgr.  These generally provide events that xssmgr reacts to.
#
#   xssmgr automatically registers some built-in on_start modules to
#   provide core functionality, such as reacting to the system being
#   idle for some time.
#
# - xssmgr_on_idle - for modules which should run once the X session
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
# - xssmgr_on_lock - for modules which should run when the lock screen
#   activates (whether due to a configured idle timeout or explicit
#   user request).
#
#   Good for enabling additional security to further lock down the
#   machine until it is unlocked.  The lock screen program itself is
#   also registered here.

# Here is a very simple configuration, which uses just two modules.
# It locks the screen after 15 minutes with i3lock.

# function xssmgr_config() {
#     xssmgr_on_idle $((15*60)) lock
#     xssmgr_on_lock i3lock
# }

# Below is a more elaborate configuration, which is close to the
# author's personal xssmgr configuration.

function xssmgr_config() {
	# Let's define some helper variables first.
	# We want a much shorter delay if the lock screen is already active.
	local delay action fade

	if (( ! xssmgr_locked ))
	then
		# Settings for when the lock screen is not active.

		# We can have different settings for different machines by
		# checking the hostname.
		if [[ "$HOSTNAME" == home.* ]]
		then
			delay=$((10 * 60))  # A longer timeout on the desktop PC.
		else
			delay=$((5 * 60))   # A shorter timeout on other machines (laptops).
		fi
		action=lock             # Lock screen after 5 or 10 minutes
		fade=60                 # Fade to black over 1 minute before locking the screen
	else
		# Settings for when the lock screen is active.

		delay=15                # Turn something off after 15 seconds

		bat_status=/sys/class/power_supply/BAT0/status
		if [[ -f "$bat_status" && "$(< $bat_status)" == "Discharging" ]]
		then
			# If running on battery, suspend the system.
			# Module parameters are passed to modules via namespaced
			# variables - see each module's documentation for what
			# parameters it accepts.
			action=power
			xssmgr_power_action=suspend
		else
			# Otherwise (AC power), just turn the screen(s) off.
			action=dpms
		fi
		fade=5                  # Fade to black over 5 seconds before turning off
	fi

	# Register our selected modules at their corresponding idle times.

	xssmgr_xbacklight_args=()
	xssmgr_xbacklight_set_args=(-time $((fade * 1000)) -fps 15)
	xssmgr_on_idle $((delay - fade)) xbacklight

	xssmgr_on_idle $delay $action

	# Register some on-lock modules, to do some more interesting things
	# when the screen is locked.  These will be started when the lock
	# screen starts, and will be stopped when the lock screen exits.

	# Prevent TTY switching.
	# No need to worry if you forgot to log out on a TTY before walking away.
	xssmgr_on_lock physlock

	# Pause dunst notifications.
	# Don't want your PMs to pop up on top of the lock screen.
	xssmgr_on_lock dunst

	# Stop udiskie.
	# Don't want to auto-mount any USB sticks while the screen is locked.
	xssmgr_on_lock udiskie

	# # Change the keyboard to US QWERTY before locking the screen.
	# # Avoid frustration due to your password not working when you were
	# # actually typing it in Cyrillic.
	# xssmgr_xkbmap_args=(-layout us)
	# xssmgr_on_lock xkbmap
	xssmgr_on_lock xkblayout

	# Finally, add the lock screen itself.  It should be the last module
	# to run, to ensure that other security modules run before the lock
	# screen becomes visible, thus confirming that the machine is secure.
	xssmgr_i3lock_args=(--show-failed-attempts --image ~/data/images/wallpaper/blurred.png)
	xssmgr_on_lock i3lock
}

# Custom on_lock xssmgr module: udiskie
# Stops udiskie, which in turn stops automounting.

function xssmgr_mod_udiskie() {
	case "$1" in
		start)
			systemctl --user stop cs-x-udiskie@:0.service
			;;
		stop)
			systemctl --user start cs-x-udiskie@:0.service
			;;
	esac
}

# Custom on_lock xssmgr module: xkblayout
# I use a custom script which replaces the entire XKB configuration,
# to avoid some programs still using QWERTY keys in their hotkey bindings.

function xssmgr_mod_xkblayout() {
	case "$1" in
		start)
			~/libexec/xkblayout 1 # US Dvorak
			;;
		stop)
			# I don't care about restoring it.
			;;
	esac
}
