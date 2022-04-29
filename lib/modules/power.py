# External on_idle xssmgr module: power
# Runs a power action on start.

def mod_power(*args):
	# Parameters:

	# The action to execute.  Should be one of suspend, hibernate,
	# hybrid-sleep, suspend-then-hibernate, or poweroff.
	power_action = module_args[0] if len(module_args) > 0 else 'suspend'

	# Implementation:

	match args[0]:
		case 'start':
			if idle_time == max_time:
				# The system is already executing a power action.
				return
			subprocess.check_call(['systemctl', power_action])
		case 'stop':
			pass
