# External on_idle xssmgr module: xbacklight
# Runs and manages an xbacklight process, which fades the screen to
# black over the configured duration.

# Additional arguments, used for both querying and setting (such as
# -ctrl or -perceived). User configurable.
if [[ ! -v xssmgr_xbacklight_args ]] ; then
	xssmgr_xbacklight_args=()
fi

# Additional arguments for fading the brightness (such as -time, -fps
# or -steps). User configurable. Generally should have -time
# corresponding to the time until the next/final idle event, and
# -steps or -fps.
if [[ ! -v xssmgr_xbacklight_set_args ]] ; then
	xssmgr_xbacklight_set_args=(-fps 15)
fi

# PID of any running xbacklight process.
xssmgr_xbacklight_pid=

# The original screen brightness.
xssmgr_xbacklight_brightness=

function xssmgr_mod_xbacklight() {
	case "$1" in
		start)
			if [[ -z "$xssmgr_xbacklight_pid" ]]
			then
				xssmgr_xbacklight_brightness=$(xbacklight "${xssmgr_xbacklight_args[@]}" -getf)
				xbacklight "${xssmgr_xbacklight_args[@]}" -set 0 "${xssmgr_xbacklight_set_args[@]}" | {
					# Get notified when it exits, so we can forget the PID
					# (so we later don't kill an innocent process due to
					# PID reuse).
					cat # Wait for EOF
					xssmgr_notify module xbacklight _exited
				} &
				xssmgr_xbacklight_pid=$!
				xssmgr_logv 'mod_xbacklight: Started xbacklight (PID %d).' "$xssmgr_xbacklight_pid"
			fi
			;;
		stop)
			if [[ -n "$xssmgr_xbacklight_pid" ]]
			then
				xssmgr_logv 'mod_xbacklight: Killing xbacklight (PID %d)...' "$xssmgr_xbacklight_pid"
				kill "$xssmgr_xbacklight_pid" || true
				xssmgr_xbacklight_pid=
				xssmgr_logv 'mod_xbacklight: Done.'
			fi
			if [[ -n "$xssmgr_xbacklight_brightness" ]]
			then
				xssmgr_logv 'mod_xbacklight: Restoring original brightness (%s).' "$xssmgr_xbacklight_brightness"
				xbacklight "${xssmgr_xbacklight_args[@]}" -set "$xssmgr_xbacklight_brightness" -steps 1 -time 0
				xssmgr_xbacklight_brightness=
			fi
			;;
		_exited)
			if [[ -n "$xssmgr_xbacklight_pid" ]]
			then
				local status=0
				wait "$xssmgr_xbacklight_pid" || status=$?
				xssmgr_logv 'mod_xbacklight: xbacklight exited with status %d.' "$status"
				xssmgr_xbacklight_pid=
			else
				xssmgr_logv 'mod_xbacklight: Ignoring stale exit notification.' "$2"
			fi
			;;
	esac
}
