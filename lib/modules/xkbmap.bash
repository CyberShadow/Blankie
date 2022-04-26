# External on_lock xssmgr module: xkbmap
# Configures the XKB map as requested when activating the lock screen,
# and restores previous settings when deactivating.

# The keyboard configuration to use when locked.  User configurable.
if [[ ! -v xssmgr_xkbmap_args ]] ; then
	xssmgr_xkbmap_args=(-layout us)
fi

# The previous keyboard configuration.
xssmgr_xkbmap_state=()

function xssmgr_mod_xkbmap() {
	case "$1" in
		start)
			# Save the old state.
			mapfile -t xssmgr_xkbmap_state < <(
				setxkbmap -query |
					sed 's/^\(.*\): *\(.*\)$/-\1\n\2/'
			)
			# Configure the locked state.
			setxkbmap "${xssmgr_xkbmap_args[@]}"
			;;
		stop)
			# Restore the old state.
			setxkbmap "${xssmgr_xkbmap_state[@]}"
			;;
	esac
}
