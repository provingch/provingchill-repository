import unittest
from unittest import mock

from monitor import (
    MAINTENANCE_AUTO_REFRESH_SECONDS,
    MaintenancePlaceholderServer,
    build_maintenance_html,
)


class MaintenancePlaceholderTests(unittest.TestCase):
    def test_build_maintenance_html_contains_expected_copy(self):
        html = build_maintenance_html()

        self.assertIn("Estamos trabajando en la pagina", html)
        self.assertIn("Modo mantenimiento activo", html)
        self.assertIn(f'content="{MAINTENANCE_AUTO_REFRESH_SECONDS}"', html)

    def test_placeholder_server_lifecycle_updates_bound_port(self):
        class FakeServer:
            def __init__(self, *_args, **_kwargs):
                self.server_address = ("127.0.0.1", 9099)
                self.daemon_threads = False
                self.shutdown_called = False
                self.close_called = False

            def serve_forever(self, **_kwargs):
                return None

            def shutdown(self):
                self.shutdown_called = True

            def server_close(self):
                self.close_called = True

        class FakeThread:
            def __init__(self, *args, **kwargs):
                self._alive = False

            def start(self):
                self._alive = True

            def is_alive(self):
                return self._alive

            def join(self, timeout=None):
                self._alive = False

        server = MaintenancePlaceholderServer(host="127.0.0.1", port=0)
        with mock.patch("monitor.ThreadingHTTPServer", FakeServer), mock.patch("monitor.Thread", FakeThread):
            self.assertTrue(server.start())
            self.assertEqual(server.host, "127.0.0.1")
            self.assertEqual(server.port, 9099)
            self.assertTrue(server.is_running)
            server.stop()
            self.assertFalse(server.is_running)


if __name__ == "__main__":
    unittest.main()
