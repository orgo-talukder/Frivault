from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from frivault.resources import resource_path


class ResourcePathTests(unittest.TestCase):
    def test_source_mode_resolves_bundled_resources(self) -> None:
        expected = Path(__file__).resolve().parents[2] / "src" / "frivault" / "resources"
        self.assertEqual(expected, resource_path())

    def test_frozen_mode_resolves_pyinstaller_resource_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            expected = Path(temporary_directory) / "frivault" / "resources" / "ui"
            with patch.object(sys, "_MEIPASS", temporary_directory, create=True):
                self.assertEqual(expected, resource_path("ui"))


if __name__ == "__main__":
    unittest.main()
