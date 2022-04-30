# xssmgr.util - utility definitions

import sys

import xssmgr

# -----------------------------------------------------------------------------
# Utility functions

def log(fmt, *args):
	sys.stderr.write('xssmgr: ' + (fmt % args) + '\n')
	sys.stderr.flush()

def logv(fmt, *args):
	if xssmgr.verbose:
		log(fmt, *args)
