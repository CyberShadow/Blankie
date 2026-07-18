import math


class Session:
	def __init__(self, idle_since):
		self.idle_since = idle_since

	def get_idle_since(self):
		return self.idle_since


def test_idle_since_uses_latest_finite_session(blankie_module, monkeypatch):
	monkeypatch.setattr(
		blankie_module.session,
		'get_sessions',
		lambda: [Session(10.0), Session(25.0), Session(15.0)],
	)

	assert blankie_module.get_idle_since() == 25.0


def test_idle_since_ignores_nan_sessions(blankie_module, monkeypatch):
	monkeypatch.setattr(
		blankie_module.session,
		'get_sessions',
		lambda: [Session(10.0), Session(math.nan), Session(25.0)],
	)

	assert blankie_module.get_idle_since() == 25.0


def test_idle_since_without_effective_session_is_infinite(blankie_module, monkeypatch):
	monkeypatch.setattr(
		blankie_module.session,
		'get_sessions',
		lambda: [Session(math.nan)],
	)

	assert blankie_module.get_idle_since() == math.inf


def test_sleeping_returns_negative_infinity(blankie_module, monkeypatch):
	blankie_module.state.sleeping = True
	monkeypatch.setattr(blankie_module.session, 'get_sessions', lambda: [Session(10.0)])

	assert blankie_module.get_idle_since() == -math.inf


def test_power_module_does_not_repeat_action_while_sleeping(blankie_module, monkeypatch):
	from blankie.modules.power import PowerModule

	blankie_module.state.sleeping = True
	called = False

	def check_call(_args):
		nonlocal called
		called = True

	monkeypatch.setattr('blankie.modules.power.subprocess.check_call', check_call)
	PowerModule().start()

	assert not called
