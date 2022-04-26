# External on_lock xssmgr module: i3lock
# Manages an i3lock instance.

# PID of the forked i3lock process.
xssmgr_i3lock_inner_pid=

# PID of the process waiting for i3lock to exit.
xssmgr_i3lock_cat_pid=

# Additional arguments. User configurable.
if [[ ! -v xssmgr_i3lock_args ]] ; then
	xssmgr_i3lock_args=()
fi

function xssmgr_mod_i3lock() {
	# Our goals:
	# - Start i3lock when this module is started.
	# - If i3lock fails to start (initialize), abort.
	# - Stop (kill) i3lock, if it is running, when this module is stopped.
	# - Exit the locked state, stopping other on_lock modules, when i3lock exits.
	case "$1" in
		start)
			if [[ -z "$xssmgr_i3lock_inner_pid" ]]
			then
				type i3lock > /dev/null # Ensure it's installed

				# Create a FIFO for the pipe used to know when i3lock exits.
				# (We use this method to avoid polling with e.g. `kill -0`.)
				local fifo="$XSSMGR_RUN_DIR"/i3lock.fifo
				rm -f "$fifo"
				mkfifo "$fifo"

				# Start a reader from the FIFO.
                # When it exits, we'll know that i3lock exited.
				xssmgr_i3lock_reader < "$fifo" &
				xssmgr_i3lock_cat_pid=$!

				# Open the write end of the FIFO.
				# This file descriptor will be inherited by i3lock.
				local i3lock_fd
				exec {i3lock_fd}> "$fifo"

				# Start i3lock.
				# We run i3lock without --nofork, and we want to know
				# the PID of the inner (forked) i3lock process, so for
				# that we also need to know the PID of the outer
				# process.
				xssmgr_logv 'mod_i3lock: Starting i3lock...'
				i3lock "${xssmgr_i3lock_args[@]}" &
				local xssmgr_i3lock_outer_pid=$!

				# Wait for the outer process to exit.
				# This signals that i3lock initialized (hopefully successfully).
				wait $xssmgr_i3lock_outer_pid

				# Find the inner process.
				xssmgr_i3lock_inner_pid=$(ps --ppid $xssmgr_i3lock_outer_pid -C i3lock -o pid | tail -n -1)
				if ! kill -0 "$xssmgr_i3lock_inner_pid"
				then
					xssmgr_log 'mod_i3lock: Failed to find the PID of the forked i3lock process.'
					exit 1
				fi

				xssmgr_logv 'mod_i3lock: Started i3lock (PID %d).' "$xssmgr_i3lock_inner_pid"

				# Close our copy of the write end of the FIFO, leaving the only copy held by i3lock.
				exec {i3lock_fd}>&-
			fi
			;;
		stop)
			if [[ -n "$xssmgr_i3lock_inner_pid" ]]
			then
				xssmgr_logv 'mod_i3lock: Killing i3lock (PID %d)...' "$xssmgr_i3lock_inner_pid"
				xssmgr_i3lock_cat_pid=  # Ignore the exit notification
				kill "$xssmgr_i3lock_inner_pid"
				while kill -0 "$xssmgr_i3lock_inner_pid" 2>/dev/null
				do
					xssmgr_logv 'mod_i3lock: Waiting...'
					sleep 0.1
				done
				xssmgr_i3lock_inner_pid=
				xssmgr_logv 'mod_i3lock: Done.'
			fi
			;;
		_exit)
			if [[ -z "$xssmgr_i3lock_cat_pid" ]]
			then
				xssmgr_logv 'mod_i3lock: Ignoring stale i3lock exit notification (not expecting one at this time, got PID %s).' \
							"$2"
			elif [[ "$2" != "$xssmgr_i3lock_cat_pid" ]]
			then
				xssmgr_logv 'mod_i3lock: Ignoring stale i3lock exit notification (wanted PID %d, got PID %s).' \
							"$xssmgr_i3lock_cat_pid" "$2"
			else
				xssmgr_log 'mod_i3lock: i3lock exited, unlocking.'
				# Unset these first, so we don't attempt to kill a
				# nonexisting process when this module is stopped.
				xssmgr_i3lock_cat_pid=
				xssmgr_i3lock_inner_pid=
				xssmgr_unlock
			fi
			;;
	esac
}

function xssmgr_i3lock_reader() {
	cat
	# If we're here, cat reached EOF, which means that all write ends
	# of the pipe were closed, which means that i3lock exited.
	xssmgr_notify module i3lock _exit "$BASHPID"
}
