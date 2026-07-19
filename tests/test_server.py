import io
import threading

import pytest


class Handler:
	def __init__(self, input, output):
		self.rfile = input
		self.wfile = output


class WakeLockInput:
	def __init__(self, trailing=b'', error=None):
		self.trailing = trailing
		self.error = error

	def readline(self):
		return b'["wake-lock"]\n'

	def read(self):
		if self.error is not None:
			raise self.error
		return self.trailing


def run_reader(module, handler):
	completed = threading.Event()
	errors = []

	def run():
		try:
			module.server_reader(handler)
		except Exception as error:
			errors.append(error)
		finally:
			completed.set()

	thread = threading.Thread(target=run)
	thread.start()
	assert completed.wait(timeout=1)
	thread.join(timeout=1)
	assert not thread.is_alive()
	return errors


def test_wake_lock_attaches_before_acknowledging(blankie_module, event_loop, monkeypatch):
	from blankie.modules.server import ServerModule

	attached = []

	def attach(spec):
		attached.append(spec)

	class Output(io.BytesIO):
		def write(self, data):
			assert attached
			return super().write(data)

	monkeypatch.setattr(blankie_module.session, 'attach', attach)
	monkeypatch.setattr(blankie_module.session, 'detach', lambda _spec: None)
	module = ServerModule()
	handler = Handler(WakeLockInput(), Output())

	assert not run_reader(module, handler)
	assert handler.wfile.getvalue() == b'Wake lock acquired.\n'
	assert len(attached) == 1


def test_wake_lock_eof_and_reset_detach_once(blankie_module, event_loop, monkeypatch):
	from blankie.modules.server import ServerModule

	for error in (None, ConnectionResetError()):
		attached = []
		detached = []
		monkeypatch.setattr(blankie_module.session, 'attach', attached.append)
		monkeypatch.setattr(blankie_module.session, 'detach', detached.append)

		run_reader(
			ServerModule(),
			Handler(WakeLockInput(error=error), io.BytesIO()),
		)

		assert detached == attached
		assert len(detached) == 1


@pytest.mark.parametrize('method', ['write', 'flush'])
def test_wake_lock_acknowledgement_failure_detaches_once(blankie_module, event_loop, monkeypatch, method):
	from blankie.modules.server import ServerModule

	attached = []
	detached = []

	class Output(io.BytesIO):
		def write(self, data):
			if method == 'write':
				raise BrokenPipeError()
			return super().write(data)

		def flush(self):
			if method == 'flush':
				raise BrokenPipeError()

	monkeypatch.setattr(blankie_module.session, 'attach', attached.append)
	monkeypatch.setattr(blankie_module.session, 'detach', detached.append)

	errors = run_reader(ServerModule(), Handler(WakeLockInput(), Output()))

	assert len(errors) == 1
	assert detached == attached
	assert len(detached) == 1


def test_simultaneous_wake_locks_use_distinct_session_specs(blankie_module, event_loop, monkeypatch):
	from blankie.modules.server import ServerModule

	attached = []
	detached = []
	both_attached = threading.Event()
	first_can_close = threading.Event()
	second_can_close = threading.Event()

	class Input(WakeLockInput):
		def __init__(self, can_close):
			super().__init__()
			self.can_close = can_close

		def read(self):
			assert self.can_close.wait(timeout=1)
			return b''

	def attach(spec):
		attached.append(spec)
		if len(attached) == 2:
			both_attached.set()

	monkeypatch.setattr(blankie_module.session, 'attach', attach)
	monkeypatch.setattr(blankie_module.session, 'detach', detached.append)
	module = ServerModule()
	threads = [
		threading.Thread(target=module.server_reader, args=(Handler(Input(event), io.BytesIO()),))
		for event in (first_can_close, second_can_close)
	]
	for thread in threads:
		thread.start()
	assert both_attached.wait(timeout=1)
	assert attached[0] != attached[1]
	assert all(spec[0] == 'session.wake_lock' for spec in attached)

	first_can_close.set()
	threads[0].join(timeout=1)
	assert not threads[0].is_alive()
	assert detached == [attached[0]]
	second_can_close.set()
	for thread in threads[1:]:
		thread.join(timeout=1)
		assert not thread.is_alive()
	assert set(detached) == set(attached)


def test_status_lists_wake_lock_sessions_without_legacy_count(blankie_module, event_loop, monkeypatch):
	from blankie.modules.server import ServerModule

	spec = ('session.wake_lock', 'client')
	monkeypatch.setattr(blankie_module.session, 'session_specs', {spec})
	monkeypatch.setattr(
		blankie_module.module,
		'get',
		lambda _spec: type('Session', (), {'get_idle_since': lambda self: float('inf')})(),
	)
	monkeypatch.setattr(blankie_module.config.configurator, 'print_status', lambda _output: None)
	handler = Handler(io.BytesIO(b'["status"]\n'), io.BytesIO())

	assert not run_reader(ServerModule(), handler)
	assert repr(spec).encode() in handler.wfile.getvalue()
	assert b'Wake locks:' not in handler.wfile.getvalue()


def test_failed_wake_lock_attach_sends_no_acknowledgement_or_detach(blankie_module, event_loop, monkeypatch):
	from blankie.modules.server import ServerModule

	detached = []
	monkeypatch.setattr(
		blankie_module.session,
		'attach',
		lambda _spec: (_ for _ in ()).throw(RuntimeError('attach failed')),
	)
	monkeypatch.setattr(blankie_module.session, 'detach', detached.append)
	handler = Handler(WakeLockInput(), io.BytesIO())

	run_reader(ServerModule(), handler)

	assert handler.wfile.getvalue() == b''
	assert not detached


def test_wake_lock_trailing_bytes_are_not_processed_as_commands(blankie_module, event_loop, monkeypatch):
	from blankie.modules.server import ServerModule

	attached = []
	detached = []
	monkeypatch.setattr(blankie_module.session, 'attach', attached.append)
	monkeypatch.setattr(blankie_module.session, 'detach', detached.append)
	handler = Handler(WakeLockInput(b'["unlock"]\n'), io.BytesIO())

	assert not run_reader(ServerModule(), handler)
	assert not blankie_module.state.locked
	assert len(attached) == 1
	assert detached == attached
