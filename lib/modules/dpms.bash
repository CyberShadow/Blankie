# External on_idle xssmgr module: dpms
# Turns off the screen(s) via the xset dpms command.

function xssmgr_mod_dpms() {
	# Parameters:

	# The DPMS state to set.  User configurable.
	# Can be one of standby, suspend, or off.
	# For most modern computer screens, the effect will be the same.
	local xssmgr_dpms_state=${xssmgr_module_args[0]-off}

	# Implementation:

	case "$1" in
		start)
			xset dpms force "$xssmgr_dpms_state"
			;;
		stop)
			xset dpms force on
			xset -dpms  # Disable default settings - we control DPMS
			;;
	esac
}
