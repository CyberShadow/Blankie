import importlib
import os
import socketserver
import sys
import threading

import pytest


def unload_blankie():
	for name in list(sys.modules):
		if name == 'blankie' or name.startswith('blankie.'):
			del sys.modules[name]


@pytest.fixture
def blankie_module(monkeypatch, tmp_path):
	home = tmp_path / 'home'
	runtime_dir = tmp_path / 'runtime'
	home.mkdir()
	runtime_dir.mkdir()
	monkeypatch.setenv('HOME', os.fspath(home))
	monkeypatch.setenv('XDG_RUNTIME_DIR', os.fspath(runtime_dir))
	monkeypatch.setenv('BLANKIE_SOCKET', os.fspath(tmp_path / 'blankie.sock'))
	unload_blankie()
	importlib.invalidate_caches()
	blankie = importlib.import_module('blankie')
	blankie.state.locked = False
	blankie.state.sleeping = False
	yield blankie
	unload_blankie()


@pytest.fixture
def event_loop(blankie_module):
	loop = blankie_module.daemon.EventLoop()
	blankie_module.daemon._event_loop = loop
	blankie_module.daemon.call = loop.call
	started = threading.Event()

	def run():
		blankie_module.daemon.event_loop_thread = threading.current_thread()
		started.set()
		loop.run()

	thread = threading.Thread(target=run)
	thread.start()
	assert started.wait(timeout=1)
	yield loop
	loop.stopping = True
	loop.call(lambda: None)
	thread.join(timeout=1)
	assert not thread.is_alive()
	blankie_module.daemon.event_loop_thread = None


@pytest.fixture
def temporary_unix_server(tmp_path):
	servers = []

	def create(handler):
		class RequestHandler(socketserver.StreamRequestHandler):
			def handle(self):
				handler(self)

		class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
			daemon_threads = True

		path = tmp_path / ('server-%d.sock' % len(servers))
		server = Server(os.fspath(path), RequestHandler)
		started = threading.Event()
		thread = threading.Thread(target=lambda: (started.set(), server.serve_forever()))
		thread.start()
		assert started.wait(timeout=1)
		servers.append((server, thread, path))
		return path

	yield create
	for server, thread, path in servers:
		server.shutdown()
		server.server_close()
		thread.join(timeout=1)
		assert not thread.is_alive()
		path.unlink(missing_ok=True)
