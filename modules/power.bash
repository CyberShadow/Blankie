# External on_idle xssmgr module: power
# Runs a power action on start.

# The action to execute.  Should be one of suspend, hibernate,
# hybrid-sleep, suspend-then-hibernate, or poweroff.
xssmgr_power_action=suspend

function xssmgr_mod_power() {
	case "$1" in
		start)
			if (( xssmgr_idle_time == xssmgr_max_time ))
			then
				# The system is already executing a power action.
				return
			fi
			systemctl "$xssmgr_power_action"
			;;
		stop)
			;;
	esac
}
