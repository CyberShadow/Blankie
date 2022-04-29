# External on_lock xssmgr module: i3lock
# Manages an i3lock instance.

def mod_i3lock(*args):
	# Our goals:
	# - Start i3lock when this module is started.
	# - If i3lock fails to start (initialize), abort.
	# - Stop (kill) i3lock, if it is running, when this module is stopped.
	# - Exit the locked state, stopping other on_lock modules, when i3lock exits.

	# Parameters:

	# Additional i3lock arguments.
	i3lock_args = module_args

	# Private state:
	s = global_state.setdefault(module_id, types.SimpleNamespace(

	    # PID of the forked i3lock process.
	    inner_pid = None,

    ))

	# Implementation:

	match args[0]:
		case 'start':
			if s.inner_pid is None:
				# Start i3lock.
				# We run i3lock without --nofork, and we want to know
				# the PID of the inner (forked) i3lock process, so for
				# that we also need to know the PID of the outer
				# process.
				logv('mod_i3lock: Starting i3lock...')
				outer = subprocess.Popen(['i3lock', *i3lock_args], stdout=subprocess.PIPE)

				# Wait for the outer process to exit.
				# This signals that i3lock initialized (hopefully successfully).
				outer.wait()
				if outer.returncode != 0:
					raise Exception('mod_i3lock: i3lock failed to start!')

				# Find the inner process.
				p = subprocess.check_output(['ps', '--ppid', str(outer.pid), '-C', 'i3lock', '-o', 'pid'])
				p = p.splitlines()[-1]
				s.inner_pid = int(p.strip())
				try:
					os.kill(s.inner_pid, 0)
				except ProcessLookupError:
					raise Exception('mod_i3lock: Failed to find the PID of the forked i3lock process.')

				# Create a thread waiting for EOF from the pipe, to know when i3lock exits.
				# (We use this method to avoid polling with e.g. `kill -0`.)
				threading.Thread(target=i3lock_reader, args=(module_id, outer.stdout, s.inner_pid,)).start()

				logv('mod_i3lock: Started i3lock (PID %d).', s.inner_pid)

		case 'stop':
			if s.inner_pid is not None:
				logv('mod_i3lock: Killing i3lock (PID %d)...', s.inner_pid)
				os.kill(s.inner_pid, signal.SIGTERM)

				while True:
					try:
						os.kill(s.inner_pid, 0)
						break
					except ProcessLookupError:
						logv('mod_i3lock: Waiting...')
						time.sleep(0.1)

				s.inner_pid = None
				logv('mod_i3lock: Done.')

		case '_exit':
			if s.inner_pid is None:
				logv('mod_i3lock: Ignoring stale i3lock exit notification (not expecting one at this time, got PID %s).',
					 args[1])
			elif args[1] != s.inner_pid:
				logv('mod_i3lock: Ignoring stale i3lock exit notification (wanted PID %d, got PID %s).',
					 s.inner_pid, args[1])
			else:
				log('mod_i3lock: i3lock exited, unlocking.')
				# Unset these first, so we don't attempt to kill a
				# nonexisting process when this module is stopped.
				s.inner_pid = None
				unlock()

def i3lock_reader(module_id, f, pid):
	f.read()
	# If we're here, f.read() reached EOF, which means that all write ends
	# of the pipe were closed, which means that i3lock exited.
	notify('module', module_id, '_exit', pid)
