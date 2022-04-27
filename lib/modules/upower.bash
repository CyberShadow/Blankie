# External on_start xssmgr module: upower
# Manages a upower --monitor instance, which receives events from the
# UPower daemon.  Used to know when the system power status changes
# (e.g. AC power is connected or disconnected), which would require
# re-evaluating xssmgr's configuration.

function xssmgr_mod_upower() {
	# Private state:

	# PID of the managed upower process.
	local -n xssmgr_upower_pid=xssmgr_${xssmgr_module_hash}_pid
	xssmgr_upower_pid=${xssmgr_upower_pid-}

	# Implementation:

	case "$1" in
		start)
			if [[ -z "$xssmgr_upower_pid" ]]
			then
				type upower > /dev/null # Ensure it's installed
				upower --monitor | xssmgr_upower_reader &
				xssmgr_upower_pid=$!
				xssmgr_logv 'mod_upower: Started upower (PID %d).' "$xssmgr_upower_pid"
			fi
			;;
		stop)
			if [[ -n "$xssmgr_upower_pid" ]]
			then
				xssmgr_logv 'mod_upower: Killing upower (PID %d)...' "$xssmgr_upower_pid"
				kill "$xssmgr_upower_pid" || true
				wait "$xssmgr_upower_pid" || true
				xssmgr_upower_pid=
				xssmgr_logv 'mod_upower: Done.'
			fi
			;;
		_ping)
			xssmgr_logv 'mod_upower: Got a line from upower, reconfiguring.'
			xssmgr_reconfigure
			;;
	esac
}

function xssmgr_upower_reader() {
	local _
	while IFS= read -r _
	do
		xssmgr_notify module "$xssmgr_module" _ping
	done
}
