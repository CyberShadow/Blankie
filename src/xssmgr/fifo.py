# xssmgr.fifo - FIFO management and sending commands
# The daemon will start a FIFO (see the 'fifo' module) which allows it
# to receive commands from other processes.

import json
import os
import stat

import xssmgr

# Path to the FIFO object.
path = os.environ.setdefault('XSSMRG_FIFO', xssmgr.run_dir + '/daemon.fifo')

# -----------------------------------------------------------------------------
# Daemon communication

# Send a line to the daemon event loop
def notify(*args):
	message = bytes(json.dumps(args) + '\n', 'utf-8')
	# Send the message in one write.
	with open(path, 'wb') as f:
		f.write(message)

	# We do this check after writing to avoid a TOCTOU.
	if not stat.S_ISFIFO(os.stat(path).st_mode):
		raise Exception('\'%s\' is not a FIFO - daemon not running?' % (path))

# Send a line to the daemon, and wait for a reply
def query(*args):
	qfifo = xssmgr.run_dir + '/query.' + str(os.getpid()) + '.fifo'  # Answer will be sent here

	os.mkfifo(qfifo, mode=0o600)
	notify(*args, qfifo)
	with open(qfifo, 'rb') as f:
		result = f.read()
	os.remove(qfifo)
	return result
