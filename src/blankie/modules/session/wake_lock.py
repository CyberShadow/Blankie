# blankie.modules.session.wake_lock - Wake-lock session

import math

import blankie


class WakeLockSession(blankie.session.Session):
	name = 'session.wake_lock'

	def __init__(self, lock_id):
		super().__init__()

	def get_idle_since(self):
		return math.inf
