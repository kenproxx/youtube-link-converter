import io
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from tools.download_progress import fetch_bytes


class DownloadProgressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                if self.path == '/forbidden':
                    self.send_error(403)
                    return
                if self.path == '/retry':
                    self.server.retry_requests += 1
                    if self.server.retry_requests == 1:
                        self.send_error(503)
                        return
                if self.path == '/waiting':
                    time.sleep(.25)
                data = b'x' * (256 * 1024)
                self.send_response(200)
                if self.path != '/unknown':
                    self.send_header('Content-Length', str(len(data) + (7 if self.path == '/truncated' else 0)))
                self.end_headers()
                try:
                    for start in range(0, len(data), 16384):
                        self.wfile.write(data[start:start + 16384])
                        self.wfile.flush()
                        time.sleep(.005)
                except (BrokenPipeError, ConnectionResetError):
                    pass
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_known_size_reports_bytes_percent_speed_and_completion(self):
        output = io.StringIO()
        data = fetch_bytes(self.base + '/known', 'Deno', stream=output, interval=.01)
        self.assertEqual(data, b'x' * (256 * 1024))
        text = output.getvalue()
        self.assertIn('Connecting', text)
        self.assertIn('100.0%', text)
        self.assertIn('MiB', text)
        self.assertIn('MiB/s', text)
        self.assertIn('ETA', text)
        self.assertIn('download complete', text)

    def test_unknown_size_does_not_invent_percentage(self):
        output = io.StringIO()
        self.assertEqual(len(fetch_bytes(self.base + '/unknown', 'Deno', stream=output, interval=.01)), 256 * 1024)
        self.assertIn('total size unknown', output.getvalue())
        self.assertNotIn('%', output.getvalue())

    def test_waiting_connection_has_heartbeat_and_bounded_deadline(self):
        output = io.StringIO()
        started = time.monotonic()
        with self.assertRaises(TimeoutError):
            fetch_bytes(self.base + '/waiting', 'Deno', stream=output,
                        interval=.01, deadline=.06, attempts=1)
        self.assertLess(time.monotonic() - started, .5)
        self.assertGreaterEqual(output.getvalue().count('Connecting'), 2)
        self.assertNotIn('download complete', output.getvalue())

    def test_access_denied_is_not_reported_as_a_success_or_retried(self):
        output = io.StringIO()
        with self.assertRaises(Exception) as raised:
            fetch_bytes(self.base + '/forbidden', 'Deno', stream=output, interval=.01)
        self.assertIn('403', str(raised.exception))
        self.assertNotIn('Retrying', output.getvalue())
        self.assertNotIn('download complete', output.getvalue())

    def test_deadline_is_honored_even_when_progress_refresh_is_slower(self):
        with self.assertRaises(TimeoutError):
            fetch_bytes(self.base + '/waiting', 'Deno', stream=io.StringIO(),
                        interval=.5, deadline=.06, attempts=1)

    def test_temporary_server_failure_retries_and_finishes(self):
        self.server.retry_requests = 0
        output = io.StringIO()
        data = fetch_bytes(self.base + '/retry', 'Deno', stream=output, interval=.01)
        self.assertEqual(len(data), 256 * 1024)
        self.assertIn('Retrying', output.getvalue())
        self.assertEqual(output.getvalue().count('download complete'), 1)

    def test_truncated_response_is_not_reported_complete(self):
        output = io.StringIO()
        with self.assertRaises(OSError):
            fetch_bytes(self.base + '/truncated', 'Deno', stream=output, interval=.01, attempts=1)
        self.assertNotIn('download complete', output.getvalue())
