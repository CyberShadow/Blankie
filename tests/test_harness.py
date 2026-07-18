import os
import socket
import threading


def test_event_loop_runs_queued_work(event_loop):
	completed = threading.Event()
	event_loop.call(completed.set)

	assert completed.wait(timeout=1)


def test_temporary_unix_server_uses_event_synchronization(temporary_unix_server):
	received = threading.Event()

	def handler(request):
		assert request.rfile.readline() == b'ping\n'
		received.set()
		request.wfile.write(b'pong\n')
		request.wfile.flush()

	path = temporary_unix_server(handler)
	with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
		client.connect(os.fspath(path))
		client.sendall(b'ping\n')
		assert received.wait(timeout=1)
		assert client.makefile('rb').readline() == b'pong\n'
