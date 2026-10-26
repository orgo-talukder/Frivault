from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from frivault.main import LocalUi


class LocalUiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        (self.root / "index.html").write_text("local", encoding="utf-8")
        self.app = LocalUi(self.root)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def request(self, path: str, method: str = "GET") -> tuple[str, dict[str, str], bytes]:
        response: dict[str, object] = {}

        def start_response(status: str, headers: list[tuple[str, str]]) -> None:
            response["status"] = status
            response["headers"] = dict(headers)

        body = b"".join(self.app({"PATH_INFO": path, "REQUEST_METHOD": method}, start_response))
        return (
            str(response["status"]),
            response["headers"],  # type: ignore[return-value]
            body,
        )

    def test_root_serves_bundled_index_with_security_headers(self) -> None:
        status, headers, body = self.request("/")
        self.assertEqual("200 OK", status)
        self.assertEqual(b"local", body)
        self.assertIn("default-src 'self'", headers["Content-Security-Policy"])
        self.assertEqual("nosniff", headers["X-Content-Type-Options"])

    def test_post_is_rejected(self) -> None:
        status, _, _ = self.request("/", "POST")
        self.assertEqual("405 Method Not Allowed", status)

    def test_missing_asset_is_not_served(self) -> None:
        status, _, _ = self.request("/missing.js")
        self.assertEqual("404 Not Found", status)

    def test_parent_path_is_rejected(self) -> None:
        outside = self.root.parent / f"{self.root.name}-secret.txt"
        outside.write_text("not served", encoding="utf-8")
        try:
            status, _, _ = self.request("/%2e%2e/secret.txt")
            self.assertEqual("404 Not Found", status)
        finally:
            outside.unlink(missing_ok=True)

    def test_head_returns_headers_without_body(self) -> None:
        status, headers, body = self.request("/", "HEAD")
        self.assertEqual("200 OK", status)
        self.assertEqual(b"", body)
        self.assertEqual("5", headers["Content-Length"])


if __name__ == "__main__":
    unittest.main()
