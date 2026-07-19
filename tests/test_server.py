import io
import json
import os
import socket
import threading

import pytest


@pytest.fixture
def server_module(blankie_module, event_loop, monkeypatch):
	from blankie.modules.server import ServerModule

	monkeypatch.setattr(blankie_module.config, 'reconfigure', lambda: None)
	monkeypatch.setattr(blankie_module.config.configurator, 'print_status', lambda _f: None)
	monkeypatch.setattr(blankie_module.session, 'attach', blankie_module.session.session_specs.add)
	monkeypatch.setattr(blankie_module.session, 'detach', blankie_module.session.session_specs.remove)
	module = ServerModule()
	module.start()
	server = module.server
	yield blankie_module, module
	if module.server is not None:
		module.stop()
	server.server_close()
	os.unlink(blankie_module.server.path)


def connect(blankie_module, *command):
	client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
	client.connect(blankie_module.server.path)
	client.sendall(json.dumps(command).encode() + b'\n')
	return client


def read_line(client):
	return client.makefile('rb', buffering=0).readline()


def reader_module(module):
	module.server = type('Server', (), {'request_lock': threading.Lock(), 'stopping': False})()
	return module


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
	module = reader_module(ServerModule())
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
			reader_module(ServerModule()),
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

	errors = run_reader(reader_module(ServerModule()), Handler(WakeLockInput(), Output()))

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
	module = reader_module(ServerModule())
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

	assert not run_reader(reader_module(ServerModule()), handler)
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

	run_reader(reader_module(ServerModule()), handler)

	assert handler.wfile.getvalue() == b''
	assert not detached


def test_wake_lock_trailing_bytes_are_not_processed_as_commands(blankie_module, event_loop, monkeypatch):
	from blankie.modules.server import ServerModule

	attached = []
	detached = []
	monkeypatch.setattr(blankie_module.session, 'attach', attached.append)
	monkeypatch.setattr(blankie_module.session, 'detach', detached.append)
	handler = Handler(WakeLockInput(b'["unlock"]\n'), io.BytesIO())

	assert not run_reader(reader_module(ServerModule()), handler)
	assert not blankie_module.state.locked
	assert len(attached) == 1
	assert detached == attached


@pytest.mark.parametrize('count', [1, 2])
def test_stop_interrupts_held_wake_lock_clients(server_module, monkeypatch, count):
	blankie_module, module = server_module
	detached = []
	detached_event = threading.Event()
	original_detach = blankie_module.session.detach

	def detach(spec):
		original_detach(spec)
		detached.append(spec)
		detached_event.set()

	monkeypatch.setattr(blankie_module.session, 'detach', detach)
	clients = [connect(blankie_module, 'wake-lock') for _ in range(count)]
	for client in clients:
		assert read_line(client) == b'Wake lock acquired.\n'
		client.settimeout(1)

	stopped = threading.Event()
	thread = threading.Thread(target=lambda: (module.stop(), stopped.set()))
	thread.start()
	try:
		assert stopped.wait(timeout=1)
		thread.join(timeout=1)
		assert not thread.is_alive()
		for client in clients:
			assert client.makefile('rb').read() == b''
	finally:
		for client in clients:
			client.close()
	assert detached_event.wait(timeout=1)
	assert len(detached) == count
	assert not blankie_module.session.session_specs
	assert module.server is None


def test_peer_close_racing_stop_detaches_once(server_module, monkeypatch):
	blankie_module, module = server_module
	detached = []
	detached_event = threading.Event()
	original_detach = blankie_module.session.detach

	def detach(spec):
		original_detach(spec)
		detached.append(spec)
		detached_event.set()

	monkeypatch.setattr(blankie_module.session, 'detach', detach)
	client = connect(blankie_module, 'wake-lock')
	assert read_line(client) == b'Wake lock acquired.\n'
	client.settimeout(1)
	close_thread = threading.Thread(target=lambda: client.shutdown(socket.SHUT_WR))
	stop_thread = threading.Thread(target=module.stop)
	close_thread.start()
	stop_thread.start()
	close_thread.join(timeout=1)
	stop_thread.join(timeout=1)
	assert not close_thread.is_alive()
	assert not stop_thread.is_alive()
	assert client.makefile('rb').read() == b''
	client.close()
	assert detached_event.wait(timeout=1)
	assert len(detached) == 1
	assert not blankie_module.session.session_specs


def test_stop_command_terminates_accept_loop(server_module, monkeypatch):
	blankie_module, module = server_module
	stopped = threading.Event()
	monkeypatch.setattr(blankie_module.daemon, 'stop', lambda: (module.stop(), stopped.set()))
	client = connect(blankie_module, 'stop')
	client.settimeout(1)
	assert client.makefile('rb').read() == b''
	assert stopped.wait(timeout=1)
	assert module.server is None
	client.close()


def test_stopping_server_does_not_start_wakeup_or_wake_lock_work(blankie_module, event_loop, monkeypatch):
	from blankie.modules.server import ServerModule

	module = ServerModule()
	module.server = type('Server', (), {'stopping': True})()
	monkeypatch.setattr(blankie_module.daemon, 'call', lambda *_args: pytest.fail('started work'))
	monkeypatch.setattr(blankie_module.session, 'attach', lambda *_args: pytest.fail('attached session'))

	assert not run_reader(module, Handler(io.BytesIO(b'["server-shutdown-ping"]\n'), io.BytesIO()))
	assert not run_reader(module, Handler(WakeLockInput(), io.BytesIO()))


def test_cleared_server_does_not_start_command_work(blankie_module, event_loop, monkeypatch):
	from blankie.modules.server import ServerModule

	monkeypatch.setattr(blankie_module.daemon, 'call', lambda *_args: pytest.fail('started work'))
	monkeypatch.setattr(blankie_module.session, 'attach', lambda *_args: pytest.fail('attached session'))

	assert not run_reader(ServerModule(), Handler(WakeLockInput(), io.BytesIO()))
	assert not run_reader(ServerModule(), Handler(io.BytesIO(b'["status"]\n'), io.BytesIO()))


def test_stop_racing_reader_admission_does_not_attach_wake_lock(server_module, monkeypatch):
	blankie_module, module = server_module
	entered = threading.Event()
	resume = threading.Event()
	completed = threading.Event()
	attached = []
	original_wake_lock = module.server_wake_lock

	def server_wake_lock(server, handler):
		entered.set()
		assert resume.wait(timeout=1)
		original_wake_lock(server, handler)
		completed.set()

	monkeypatch.setattr(module, 'server_wake_lock', server_wake_lock)
	monkeypatch.setattr(blankie_module.session, 'attach', attached.append)
	client = connect(blankie_module, 'wake-lock')
	assert entered.wait(timeout=1)
	stop_thread = threading.Thread(target=module.stop)
	stop_thread.start()
	stop_thread.join(timeout=1)
	assert not stop_thread.is_alive()
	resume.set()
	assert client.makefile('rb').read() == b''
	client.close()
	assert completed.wait(timeout=1)
	assert not attached


def test_detach_during_shutdown_drain_does_not_restart_modules(blankie_module, event_loop, monkeypatch):
	spec = ('session.wake_lock', 'shutdown')
	attached = threading.Event()
	detached = threading.Event()

	monkeypatch.setitem(blankie_module.module.selectors, '95-shutdown', blankie_module.daemon.shutdown_selector)
	monkeypatch.setattr(blankie_module.module, 'running_modules', [])
	monkeypatch.setattr(blankie_module.module, 'update', lambda: None)
	blankie_module.daemon.call(blankie_module.session.attach, spec)
	blankie_module.daemon.call(attached.set)
	assert attached.wait(timeout=1)
	blankie_module.daemon.call(blankie_module.session.detach, spec)
	blankie_module.daemon.call(detached.set)
	assert detached.wait(timeout=1)
	assert not blankie_module.session.session_specs
	assert not blankie_module.module.running_modules


def test_detach_queued_after_event_loop_exit_does_not_block_stop(blankie_module, monkeypatch):
	from blankie.modules.server import ServerModule

	loop = blankie_module.daemon.EventLoop()
	blankie_module.daemon._event_loop = loop
	blankie_module.daemon.call = loop.call
	started = threading.Event()

	def run():
		blankie_module.daemon.event_loop_thread = threading.current_thread()
		started.set()
		loop.run()

	loop_thread = threading.Thread(target=run)
	loop_thread.start()
	assert started.wait(timeout=1)
	loop.call(lambda: setattr(loop, 'stopping', True))
	loop_thread.join(timeout=1)
	assert not loop_thread.is_alive()

	module = ServerModule()
	module.server = type('Server', (), {'interrupt_requests': lambda self: None})()
	module.server_thread = type('Thread', (), {'join': lambda self: None})()
	monkeypatch.setattr(blankie_module.server, 'notify', lambda *_args: None)
	spec = ('session.wake_lock', 'stopped-loop')
	blankie_module.session.session_specs.add(spec)
	released = threading.Event()
	blankie_module.daemon.call(blankie_module.session.detach, spec)
	blankie_module.daemon.call(released.set)
	module.stop()
	assert not released.is_set()
	assert spec in blankie_module.session.session_specs
