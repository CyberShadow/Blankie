# External on_lock xssmgr module: physlock
# Disables TTY switching, to prevent switching to another (possibly
# unlocked) TTY while the lock screen is active.

function xssmgr_mod_physlock() {
	case "$1" in
		start)
			physlock -l
			;;
		stop)
			physlock -L
			;;
	esac
}
