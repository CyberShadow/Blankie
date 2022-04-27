# External on_idle xssmgr module: xbacklight
# Runs and manages an xbacklight process, which fades the screen to
# black over the configured duration.

function xssmgr_mod_xbacklight() {
	# Parameters:

	# Additional arguments, used for both querying and setting (such as
	# -ctrl or -perceived).
	local xssmgr_xbacklight_args=()

	# Additional arguments for fading the brightness (such as -time,
	# -fps or -steps). Generally should have -time corresponding to
	# the time until the next/final idle event, and -steps or -fps.
	local xssmgr_xbacklight_set_args=()

	# Sort module arguments into the above.
	local i
	for (( i=0; i < ${#xssmgr_module_args[@]}; ))
	do
		case "${xssmgr_module_args[$i]}" in
			-ctrl|-display|-perceived)
				xssmgr_xbacklight_args+=("${xssmgr_module_args[$i]}" "${xssmgr_module_args[$((i+1))]}")
				i=$((i+2))
				;;
			*)
				xssmgr_xbacklight_set_args+=("${xssmgr_module_args[$i]}")
				i=$((i+1))
				;;
		esac
	done

	# Private state:

	# PID of any running xbacklight process.
	local -n xssmgr_xbacklight_pid=xssmgr_${xssmgr_module_hash}_pid
	xssmgr_xbacklight_pid=${xssmgr_xbacklight_pid-}

	# The original screen brightness.
	local -n xssmgr_xbacklight_brightness=xssmgr_${xssmgr_module_hash}_brightness
	xssmgr_xbacklight_brightness=${xssmgr_xbacklight_brightness-}

	# Implementation:

	case "$1" in
		start)
			if [[ -z "$xssmgr_xbacklight_pid" ]]
			then
				xssmgr_xbacklight_brightness=$(xbacklight "${xssmgr_xbacklight_args[@]}" -getf)
				xssmgr_logv 'mod_xbacklight: Got original brightness (%s).' "$xssmgr_xbacklight_brightness"
				local args=(xbacklight "${xssmgr_xbacklight_args[@]}" -set 0 "${xssmgr_xbacklight_set_args[@]}")
				xssmgr_logv 'mod_xbacklight: Running:%s' "$(printf ' %q' "${args[@]}")"
				"${args[@]}" > >(
					# Get notified when it exits, so we can forget the PID
					# (so we later don't kill an innocent process due to
					# PID reuse).
					cat # Wait for EOF
					xssmgr_notify module "$xssmgr_module" _exited
				) &
				xssmgr_xbacklight_pid=$!
				xssmgr_logv 'mod_xbacklight: Started xbacklight (PID %d).' "$xssmgr_xbacklight_pid"
			fi
			;;
		stop)
			if [[ -n "$xssmgr_xbacklight_pid" ]]
			then
				xssmgr_logv 'mod_xbacklight: Killing xbacklight (PID %d)...' "$xssmgr_xbacklight_pid"
				kill "$xssmgr_xbacklight_pid" || true
				wait "$xssmgr_xbacklight_pid" || true
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
				xssmgr_logv 'mod_xbacklight: Ignoring stale exit notification.'
			fi
			;;
	esac
}
