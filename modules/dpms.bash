# External on_idle xssmgr module: dpms
# Turns off the screen(s) via the xset dpms command.

# The DPMS state to set.  User configurable.
# Can be one of standby, suspend, or off.
# For most modern computer screens, the effect will be the same.
xssmgr_dpms_state=off

function xssmgr_mod_dpms() {
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
