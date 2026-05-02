from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import patch

import main


class TestMainModes(unittest.TestCase):
    @patch("main.run_base_testbench")
    @patch("main.parse_args")
    def test_main_dispatches_testbench_mode(self, mock_parse_args: Any, mock_run_testbench: Any) -> None:
        class _Args:
            mode = "testbench"

        mock_parse_args.return_value = _Args()

        main.main()

        mock_run_testbench.assert_called_once()


if __name__ == "__main__":
    unittest.main()
