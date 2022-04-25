# External on_lock xssmgr module: dunst
# Pauses dunst notifications, preventing them from being displayed on
# top of the lock screen.

function xssmgr_mod_dunst() {
	case "$1" in
		start)
			dunstctl set-paused true
			;;
		stop)
			dunstctl set-paused false
			;;
	esac
}
