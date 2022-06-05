# blankie.logging - logging implementation

import logging
import os

# Define a few severity levels specific to Blankie
TRACE = logging.DEBUG - 5
SECURITY = logging.ERROR - 5

logging.addLevelName(TRACE, 'TRACE')
logging.addLevelName(SECURITY, 'SECURITY')

# Define a class which implements the severity levels as methods
class Logger(logging.getLoggerClass()):
	def trace(self, *args, **kwargs):
		self.log(TRACE, *args, **kwargs)

	def security(self, *args, **kwargs):
		self.log(SECURITY, *args, **kwargs)

logging.setLoggerClass(Logger)

logging.basicConfig(
	format=os.getenv('XSSMGR_LOG_FORMAT', '%(name)s: %(message)s'),
	level=[
		logging.CRITICAL,
		logging.ERROR,
		SECURITY,
		logging.WARNING,
		logging.INFO,
		logging.DEBUG,
		TRACE,
	][4 + int(os.getenv('XSSMGR_VERBOSE', '0'))]
)
log = logging.getLogger('blankie')
