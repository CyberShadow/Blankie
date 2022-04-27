# External on_idle xssmgr module: power
# Runs a power action on start.

function xssmgr_mod_power() {
	# Parameters:

	# The action to execute.  Should be one of suspend, hibernate,
	# hybrid-sleep, suspend-then-hibernate, or poweroff.
	local xssmgr_power_action=${xssmgr_module_args[0]-suspend}

	# Implementation:

	case "$1" in
		start)
			if (( xssmgr_idle_time == xssmgr_max_time ))
			then
				# The system is already executing a power action.
				return 0
			fi
			systemctl "$xssmgr_power_action"
			;;
		stop)
			;;
	esac
}
