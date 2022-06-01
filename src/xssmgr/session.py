# xssmgr.session - session management

import xssmgr
from xssmgr.logging import log

# -----------------------------------------------------------------------------
# Session management

# A session represents an xssmgr connection to a user session, which
# can be e.g. an X11 server instance or a Linux console / TTY.
# xssmgr aggregates data (idleness) from all sessions, and acts
# (locking/unlocking) on all sessions.

# We implement sessions as modules, to take advantage of the existing
# module dependency and cleanup mechanisms.

class Session(xssmgr.module.Module):
	# Return this session's idle time in seconds.
	# If this session cannot, in its current state (i.e. until the
	# next call to invalidate), become idle, no matter how much time
	# will pass (e.g. due to a "wake-lock"), this can be indicated by
	# returning -math.inf.
	def get_idle_time(self):
		raise NotImplementedError()

	# Requests that the next call to get_idle_time returns fresh
	# results.
	def invalidate(self):
		pass

	# Ensure that PerSessionModuleLauncher instances have their lists
	# synchronized.
	def start(self):
		xssmgr.module.update()

	def stop(self):
		xssmgr.module.update()


# This controls which Session modules should be running right now
# (using the module selector below).
session_specs = set()


# Selector which keeps the session modules running.
def session_selector(wanted_modules):
	wanted_modules.extend(session_specs)

xssmgr.module.selectors['30-sessions'] = session_selector


def attach(session_spec):
	if session_spec in session_specs:
		raise xssmgr.UserError('Already attached to this session')

	try:
		session_specs.add(session_spec)
		xssmgr.module.update()
	except:
		session_specs.remove(session_spec)
		xssmgr.module.update()
		raise


def detach(session_spec):
	if session_spec not in session_specs:
		raise xssmgr.UserError('Already not attached to this session')

	session_specs.remove(session_spec)
	xssmgr.module.update()


# Get all running Session objects.
def get_sessions():
	return [xssmgr.module.get(spec) for spec in session_specs]

# -----------------------------------------------------------------------------
# Per-session modules

# Helper class, defines a module which runs some other module class
# once for each running session of a type.  Parameters are forwarded
# to the module, with the session spec tuple (e.g. ("session.x11",
# ":0")) prepended.  Subclasses should just declare the name,
# per_session_name, and session_type.

class PerSessionModuleLauncher(xssmgr.module.Module):
	# Name of the module to run (once per session).
	# Define this in the subclass.
	per_session_name = None

	# Name of the session module.
	# Define this in the subclass.
	session_type = None

	def __init__(self, *args):
		self.per_session_module_args = args
		super().__init__()

	def per_session_selector(self, wanted_modules):
		for module_spec in xssmgr.module.running_modules:
			if module_spec[0] == self.session_type:
				wanted_modules.append((self.per_session_name, module_spec, *self.per_session_module_args))

	def per_session_selector_key(self):
		return '40-' + repr(self) + '-' + self.session_type + '-' + self.name

	def start(self):
		xssmgr.module.selectors[self.per_session_selector_key()] = self.per_session_selector
		xssmgr.module.update()

	def stop(self):
		del xssmgr.module.selectors[self.per_session_selector_key()]
		xssmgr.module.update()


# -----------------------------------------------------------------------------
# Remote (CLI -> server) actions:

# Returns a module spec suitable for attaching to the invoking
# process's session, or None.
def get_session():
	from xssmgr.modules.session import x11, console
	return \
		x11.get_session() or \
		console.get_session() or \
		None

# Ask the xssmgr daemon to attach/detach to/from the given session that the
# current process is running in.
def remote_attach_or_detach(do_attach, session_spec=None):
	if session_spec is None:
		session_spec = get_session()
	if session_spec is None:
		raise xssmgr.UserError('No session detected.')
	result = xssmgr.server.query('attach' if do_attach else 'detach', *session_spec)
	if result == b'ok':
		log.info('Attached to %r' if do_attach else 'Detached from %r', session_spec)
	else:
		log.critical('Failed to %s %r: %s',
					 'attach to' if do_attach else 'detach from',
					 session_spec, result)
