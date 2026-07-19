import io
import os
import socket
import sys
import threading

import pytest


class WakeLockSocket:
	def __init__(self, acknowledgement, read_error=None):
		self.acknowledgement = acknowledgement
		self.read_error = read_error
		self.closed = False
		self.shutdown_calls = []

	def shutdown(self, how):
		self.shutdown_calls.append(how)

	def makefile(self, _mode):
		return self

	def readline(self):
		return self.acknowledgement

	def read(self):
		if self.read_error:
			raise self.read_error
		return b''

	def close(self):
		self.closed = True

	def __enter__(self):
		return self

	def __exit__(self, *_args):
		self.close()


@pytest.fixture
def wake_lock_server(blankie_module, event_loop, monkeypatch):
	from blankie.modules.server import ServerModule

	monkeypatch.setattr(blankie_module.config, 'reconfigure', lambda: None)
	monkeypatch.setattr(blankie_module.config.configurator, 'print_status', lambda _f: None)
	attached_specs = []
	detached_specs = []
	attached = threading.Event()
	detached = threading.Event()

	def attach(spec):
		blankie_module.session.session_specs.add(spec)
		attached_specs.append(spec)
		attached.set()

	def detach(spec):
		blankie_module.session.session_specs.remove(spec)
		detached_specs.append(spec)
		detached.set()

	monkeypatch.setattr(blankie_module.session, 'attach', attach)
	monkeypatch.setattr(blankie_module.session, 'detach', detach)
	module = ServerModule()
	module.start()
	server = module.server
	yield blankie_module, module, attached_specs, detached_specs, attached, detached
	if module.server is not None:
		module.stop()
	server.server_close()
	os.unlink(blankie_module.server.path)


class ObservedWakeLockFile:
	def __init__(self, file, acknowledged, release=None, error=None):
		self.file = file
		self.acknowledged = acknowledged
		self.release = release
		self.error = error

	def __enter__(self):
		return self

	def __exit__(self, *_args):
		self.file.close()

	def readline(self):
		acknowledgement = self.file.readline()
		self.acknowledged.set()
		return acknowledgement

	def read(self):
		if self.error is not None:
			assert self.release.wait(timeout=1)
			raise self.error
		return self.file.read()


class ObservedWakeLockSocket:
	def __init__(self, socket, acknowledged, release=None, error=None):
		self.socket = socket
		self.acknowledged = acknowledged
		self.release = release
		self.error = error
		self.shutdown_calls = []
		self.closed = threading.Event()

	def __enter__(self):
		return self

	def __exit__(self, *_args):
		self.close()

	def shutdown(self, how):
		self.shutdown_calls.append(how)
		self.socket.shutdown(how)

	def close(self):
		self.socket.close()
		self.closed.set()

	def makefile(self, mode):
		return ObservedWakeLockFile(
			self.socket.makefile(mode), self.acknowledged, self.release, self.error)


def start_wake_lock_client(blankie_module, monkeypatch, acknowledged, release=None, error=None):
	clients = []
	original_send = blankie_module.server._send

	def send(*args):
		socket = original_send(*args)
		if args == ('wake-lock',):
			client = ObservedWakeLockSocket(socket, acknowledged, release, error)
			clients.append(client)
			return client
		return socket

	monkeypatch.setattr(blankie_module.server, '_send', send)
	completed = threading.Event()
	errors = []

	def run():
		try:
			blankie_module.server.wake_lock()
		except BaseException as error:
			errors.append(error)
		finally:
			completed.set()

	thread = threading.Thread(target=run)
	thread.start()
	return clients, completed, errors, thread


def test_wake_lock_sends_command_acknowledges_and_waits_for_daemon_eof(blankie_module, temporary_unix_server, capsys):
	command_received = threading.Event()
	allow_eof = threading.Event()

	def handler(request):
		assert request.rfile.readline() == b'["wake-lock"]\n'
		command_received.set()
		request.wfile.write(b'Wake lock acquired.\n')
		request.wfile.flush()
		assert allow_eof.wait(timeout=1)

	blankie_module.server.path = str(temporary_unix_server(handler))
	completed = threading.Event()
	thread = threading.Thread(target=lambda: (blankie_module.server.wake_lock(), completed.set()))
	thread.start()

	assert command_received.wait(timeout=1)
	assert not completed.is_set()
	allow_eof.set()
	thread.join(timeout=1)
	assert not thread.is_alive()
	assert capsys.readouterr().out == 'Wake lock acquired.\n'


def test_wake_lock_daemon_eof_detaches_its_session_without_half_close(wake_lock_server, monkeypatch):
	blankie_module, module, attached_specs, detached_specs, attached, detached = wake_lock_server
	acknowledged = threading.Event()
	clients, completed, errors, thread = start_wake_lock_client(blankie_module, monkeypatch, acknowledged)

	assert acknowledged.wait(timeout=1)
	assert attached.wait(timeout=1)
	spec, = attached_specs
	assert spec in blankie_module.session.session_specs
	module.stop()
	assert completed.wait(timeout=1)
	thread.join(timeout=1)
	assert not thread.is_alive()
	assert not errors
	assert clients[0].shutdown_calls == []
	assert clients[0].closed.is_set()
	assert detached.wait(timeout=1)
	assert detached_specs == [spec]
	assert spec not in blankie_module.session.session_specs


@pytest.mark.parametrize('error_type', [ConnectionResetError, KeyboardInterrupt])
def test_wake_lock_read_failures_detach_its_session_without_half_close(wake_lock_server, monkeypatch, error_type):
	blankie_module, _module, attached_specs, detached_specs, attached, detached = wake_lock_server
	acknowledged = threading.Event()
	release = threading.Event()
	error = error_type()
	clients, completed, errors, thread = start_wake_lock_client(
		blankie_module, monkeypatch, acknowledged, release, error)

	assert acknowledged.wait(timeout=1)
	assert attached.wait(timeout=1)
	spec, = attached_specs
	assert spec in blankie_module.session.session_specs
	release.set()
	assert completed.wait(timeout=1)
	thread.join(timeout=1)
	assert not thread.is_alive()
	assert errors == [error]
	assert clients[0].shutdown_calls == []
	assert clients[0].closed.is_set()
	assert detached.wait(timeout=1)
	assert detached_specs == [spec]
	assert spec not in blankie_module.session.session_specs


@pytest.mark.parametrize('acknowledgement', [b'', b'Wake lock acquired\n', b'nope\n'])
def test_wake_lock_rejects_bad_acknowledgement_and_closes_socket(blankie_module, monkeypatch, acknowledgement):
	client = WakeLockSocket(acknowledgement)
	monkeypatch.setattr(blankie_module.server, '_send', lambda *_args: client)

	with pytest.raises(blankie_module.UserError, match='Failed to acquire wake lock'):
		blankie_module.server.wake_lock()

	assert client.closed
	assert client.shutdown_calls == []


@pytest.mark.parametrize('error', [ConnectionResetError(), KeyboardInterrupt()])
def test_wake_lock_closes_on_read_error_or_interrupt(blankie_module, monkeypatch, error):
	client = WakeLockSocket(b'Wake lock acquired.\n', error)
	monkeypatch.setattr(blankie_module.server, '_send', lambda *_args: client)

	with pytest.raises(type(error)):
		blankie_module.server.wake_lock()

	assert client.closed
	assert client.shutdown_calls == []


def test_wake_lock_flushes_before_waiting_for_eof(blankie_module, monkeypatch):
	entered_read = threading.Event()
	allow_eof = threading.Event()

	class Output(io.StringIO):
		def __init__(self):
			super().__init__()
			self.flushed = threading.Event()

		def flush(self):
			self.flushed.set()
			super().flush()

	class BlockingSocket(WakeLockSocket):
		def read(self):
			entered_read.set()
			assert allow_eof.wait(timeout=1)
			return b''

	client = BlockingSocket(b'Wake lock acquired.\n')
	output = Output()
	monkeypatch.setattr(blankie_module.server, '_send', lambda *_args: client)
	monkeypatch.setattr(sys, 'stdout', output)
	thread = threading.Thread(target=blankie_module.server.wake_lock)
	thread.start()

	assert entered_read.wait(timeout=1)
	assert output.flushed.is_set()
	assert output.getvalue() == 'Wake lock acquired.\n'
	allow_eof.set()
	thread.join(timeout=1)
	assert not thread.is_alive()
	assert client.closed
	assert client.shutdown_calls == []


def test_send_serializes_before_opening_a_connection(blankie_module, monkeypatch):
	monkeypatch.setattr(blankie_module.server.socket, 'socket', lambda *_args: pytest.fail('must not open'))

	with pytest.raises(TypeError):
		blankie_module.server._send(object())


def test_send_writes_the_complete_command_after_short_writes(blankie_module, monkeypatch):
	class Client:
		def __init__(self):
			self.received = b''

		def connect(self, _path):
			pass

		def send(self, message):
			self.received += message[:1]
			return 1

		def sendall(self, message):
			while message:
				written = self.send(message)
				message = message[written:]

	client = Client()
	monkeypatch.setattr(blankie_module.server.socket, 'socket', lambda *_args: client)

	assert blankie_module.server._send('wake-lock') is client
	assert client.received == b'["wake-lock"]\n'


def test_main_wake_lock_invokes_helper_without_arguments(blankie_module, monkeypatch):
	called = []
	monkeypatch.setattr(blankie_module.config, 'load', lambda: None)
	monkeypatch.setattr(blankie_module.server, 'wake_lock', lambda: called.append(True))
	monkeypatch.setattr(sys, 'argv', ['blankie', 'wake-lock'])

	assert blankie_module.main() == 0
	assert called == [True]


def test_main_wake_lock_rejects_arguments_without_connecting(blankie_module, monkeypatch):
	monkeypatch.setattr(blankie_module.config, 'load', lambda: None)
	monkeypatch.setattr(blankie_module.server, 'wake_lock', lambda: pytest.fail('must not connect'))
	monkeypatch.setattr(sys, 'argv', ['blankie', 'wake-lock', 'unexpected'])

	assert blankie_module.main() == 1


def test_help_advertises_hyphenated_wake_lock_command(blankie_module, monkeypatch, capsys):
	monkeypatch.setattr(sys, 'argv', ['blankie', 'help'])

	assert blankie_module.main() == 0
	assert 'wake-lock    Inhibit locking and suspend until this command exits.' in capsys.readouterr().out

	monkeypatch.setattr(blankie_module.config, 'load', lambda: None)
	monkeypatch.setattr(blankie_module.server, '_send', lambda *_args: pytest.fail('must not connect'))
	monkeypatch.setattr(sys, 'argv', ['blankie', 'wake_lock'])
	assert blankie_module.main() == 1


def test_notify_and_query_keep_their_socket_lifecycles(blankie_module, monkeypatch):
	class Client:
		def __init__(self):
			self.shutdown_calls = []
			self.closed = False

		def shutdown(self, how):
			self.shutdown_calls.append(how)

		def makefile(self, _mode):
			return io.BytesIO(b'reply')

		def close(self):
			self.closed = True

	notify_client = Client()
	query_client = Client()
	clients = iter([notify_client, query_client])
	monkeypatch.setattr(blankie_module.server, '_send', lambda *_args: next(clients))

	blankie_module.server.notify('reload')
	assert notify_client.shutdown_calls == []
	assert notify_client.closed
	assert blankie_module.server.query('status') == b'reply'
	assert query_client.shutdown_calls == [socket.SHUT_WR]
	assert query_client.closed
