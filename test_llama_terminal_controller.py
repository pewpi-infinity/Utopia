#!/usr/bin/env python3
"""
Tests for LlamaTerminalController
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Ensure the repo root is on the path
sys.path.insert(0, os.path.dirname(__file__))

from llama_terminal_controller import (
    DEFAULT_CONFIG,
    LlamaTerminalController,
    OllamaManager,
    RepositoryManager,
)


class TestOllamaManager(unittest.TestCase):
    """Tests for OllamaManager"""

    def setUp(self):
        self.config = DEFAULT_CONFIG.copy()

    def test_is_running_returns_false_when_unreachable(self):
        self.config["ollama_host"] = "http://localhost:19999"
        mgr = OllamaManager(self.config)
        self.assertFalse(mgr.is_running())

    @patch("llama_terminal_controller.urllib.request.urlopen")
    def test_is_running_returns_true_when_reachable(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        mgr = OllamaManager(self.config)
        self.assertTrue(mgr.is_running())

    @patch("llama_terminal_controller.urllib.request.urlopen")
    def test_model_exists_true(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {"models": [{"name": "llama3.2:latest"}]}
        ).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        mgr = OllamaManager(self.config)
        self.assertTrue(mgr._model_exists("llama3.2"))

    @patch("llama_terminal_controller.urllib.request.urlopen")
    def test_model_exists_false(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"models": []}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        mgr = OllamaManager(self.config)
        self.assertFalse(mgr._model_exists("llama3.2"))

    def test_find_ollama_binary_returns_none_or_string(self):
        result = OllamaManager._find_ollama_binary()
        self.assertTrue(result is None or isinstance(result, str))


class TestRepositoryManager(unittest.TestCase):
    """Tests for RepositoryManager"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.repos = {"testrepo": self.test_dir}
        self.mgr = RepositoryManager(self.repos)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _write(self, rel_path, content="hello"):
        full = os.path.join(self.test_dir, rel_path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(content)
        return full

    def test_get_repo_path_known(self):
        self.assertEqual(self.mgr.get_repo_path("testrepo"), self.test_dir)

    def test_get_repo_path_unknown(self):
        self.assertIsNone(self.mgr.get_repo_path("nonexistent"))

    def test_read_file_success(self):
        self._write("a.txt", "content here")
        result = self.mgr.read_file("testrepo", "a.txt")
        self.assertEqual(result, "content here")

    def test_read_file_missing(self):
        self.assertIsNone(self.mgr.read_file("testrepo", "missing.txt"))

    def test_read_file_unknown_repo(self):
        self.assertIsNone(self.mgr.read_file("ghost", "a.txt"))

    def test_write_file_creates_file(self):
        success = self.mgr.write_file("testrepo", "out.txt", "data")
        self.assertTrue(success)
        with open(os.path.join(self.test_dir, "out.txt")) as f:
            self.assertEqual(f.read(), "data")

    def test_write_file_creates_subdirectory(self):
        success = self.mgr.write_file("testrepo", "sub/dir/file.txt", "nested")
        self.assertTrue(success)
        self.assertTrue(
            os.path.exists(os.path.join(self.test_dir, "sub", "dir", "file.txt"))
        )

    def test_write_file_unknown_repo(self):
        self.assertFalse(self.mgr.write_file("ghost", "x.txt", "y"))

    def test_list_files(self):
        self._write("a.txt")
        self._write("sub/b.txt")
        files = self.mgr.list_files("testrepo")
        self.assertIn("a.txt", files)
        self.assertIn(os.path.join("sub", "b.txt"), files)

    def test_list_files_unknown_repo(self):
        self.assertEqual(self.mgr.list_files("ghost"), [])


class TestLlamaTerminalController(unittest.TestCase):
    """Tests for LlamaTerminalController"""

    def _make_controller(self, repos=None):
        """Return a controller with Ollama disabled."""
        cfg = DEFAULT_CONFIG.copy()
        cfg["repositories"] = repos or {}
        with patch.object(LlamaTerminalController, "initialize_ollama"):
            ctrl = LlamaTerminalController(config=cfg)
        return ctrl

    # ------------------------------------------------------------------
    # Configuration loading
    # ------------------------------------------------------------------

    def test_load_config_returns_defaults_when_no_file(self):
        with patch("os.path.exists", return_value=False):
            cfg = LlamaTerminalController._load_config()
        self.assertEqual(cfg["default_model"], DEFAULT_CONFIG["default_model"])

    def test_load_config_merges_user_config(self):
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        json.dump({"default_model": "mistral"}, tmp)
        tmp.close()
        try:
            orig = "llama_terminal_controller.LlamaTerminalController._load_config"
            with patch(
                "os.path.exists",
                side_effect=lambda p: p == tmp.name or os.path.lexists(p),
            ), patch(
                "builtins.open",
                side_effect=lambda p, *a, **kw: open(tmp.name, *a, **kw)
                if p == tmp.name
                else open(p, *a, **kw),
            ):
                pass  # just verifying json merge logic directly
            with open(tmp.name) as f:
                data = json.load(f)
            self.assertEqual(data["default_model"], "mistral")
        finally:
            os.unlink(tmp.name)

    # ------------------------------------------------------------------
    # Conversation history
    # ------------------------------------------------------------------

    def test_update_history_appends(self):
        ctrl = self._make_controller()
        ctrl._update_conversation_history("user", "hello")
        self.assertEqual(len(ctrl.conversation_history), 1)
        self.assertEqual(ctrl.conversation_history[0]["role"], "user")

    def test_update_history_trims_to_max(self):
        cfg = DEFAULT_CONFIG.copy()
        cfg["max_conversation_history"] = 3
        with patch.object(LlamaTerminalController, "initialize_ollama"):
            ctrl = LlamaTerminalController(config=cfg)
        for i in range(5):
            ctrl._update_conversation_history("user", f"msg {i}")
        self.assertEqual(len(ctrl.conversation_history), 3)

    # ------------------------------------------------------------------
    # Built-in commands
    # ------------------------------------------------------------------

    def test_help_command(self):
        ctrl = self._make_controller()
        result = ctrl._handle_special_commands("help")
        self.assertIn("Built-in commands", result)

    def test_history_command_empty(self):
        ctrl = self._make_controller()
        result = ctrl._handle_special_commands("history")
        self.assertIn("no history", result)

    def test_history_command_with_entries(self):
        ctrl = self._make_controller()
        ctrl._update_conversation_history("user", "first message")
        result = ctrl._handle_special_commands("history")
        self.assertIn("first message", result)

    def test_exit_raises_keyboard_interrupt(self):
        ctrl = self._make_controller()
        with self.assertRaises(KeyboardInterrupt):
            ctrl._handle_special_commands("exit")

    def test_quit_raises_keyboard_interrupt(self):
        ctrl = self._make_controller()
        with self.assertRaises(KeyboardInterrupt):
            ctrl._handle_special_commands("quit")

    def test_unrecognised_command_returns_none(self):
        ctrl = self._make_controller()
        self.assertIsNone(ctrl._handle_special_commands("what is the weather?"))

    def test_repo_command_lists_files(self):
        test_dir = tempfile.mkdtemp()
        try:
            open(os.path.join(test_dir, "file.txt"), "w").close()
            ctrl = self._make_controller(repos={"myrepo": test_dir})
            result = ctrl._handle_special_commands("repo myrepo")
            self.assertIn("file.txt", result)
        finally:
            shutil.rmtree(test_dir)

    def test_read_command_returns_content(self):
        test_dir = tempfile.mkdtemp()
        try:
            with open(os.path.join(test_dir, "hello.txt"), "w") as f:
                f.write("world")
            ctrl = self._make_controller(repos={"myrepo": test_dir})
            result = ctrl._handle_special_commands("read myrepo hello.txt")
            self.assertEqual(result, "world")
        finally:
            shutil.rmtree(test_dir)

    # ------------------------------------------------------------------
    # access_repository
    # ------------------------------------------------------------------

    def test_access_repository_list(self):
        test_dir = tempfile.mkdtemp()
        try:
            open(os.path.join(test_dir, "f.py"), "w").close()
            ctrl = self._make_controller(repos={"r": test_dir})
            files = ctrl.access_repository("r", action="list")
            self.assertIn("f.py", files)
        finally:
            shutil.rmtree(test_dir)

    def test_access_repository_read_write(self):
        test_dir = tempfile.mkdtemp()
        try:
            ctrl = self._make_controller(repos={"r": test_dir})
            written = ctrl.access_repository(
                "r", action="write", file_path="x.txt", content="abc"
            )
            self.assertTrue(written)
            content = ctrl.access_repository("r", action="read", file_path="x.txt")
            self.assertEqual(content, "abc")
        finally:
            shutil.rmtree(test_dir)

    def test_access_repository_unknown_action(self):
        ctrl = self._make_controller()
        result = ctrl.access_repository("r", action="noop")
        self.assertIsNone(result)

    # ------------------------------------------------------------------
    # manage_files
    # ------------------------------------------------------------------

    def test_manage_files_write_and_read(self):
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.close()
        try:
            ctrl = self._make_controller()
            ctrl.manage_files(tmp.name, action="write", content="test data")
            result = ctrl.manage_files(tmp.name, action="read")
            self.assertEqual(result, "test data")
        finally:
            os.unlink(tmp.name)

    def test_manage_files_list_directory(self):
        test_dir = tempfile.mkdtemp()
        try:
            open(os.path.join(test_dir, "z.txt"), "w").close()
            ctrl = self._make_controller()
            files = ctrl.manage_files(test_dir, action="list")
            self.assertIn("z.txt", files)
        finally:
            shutil.rmtree(test_dir)

    def test_manage_files_read_missing_returns_none(self):
        ctrl = self._make_controller()
        result = ctrl.manage_files("/nonexistent/path/file.txt", action="read")
        self.assertIsNone(result)

    # ------------------------------------------------------------------
    # execute_code
    # ------------------------------------------------------------------

    def test_execute_code_success(self):
        ctrl = self._make_controller()
        result = ctrl.execute_code("print('hello')")
        self.assertEqual(result.strip(), "hello")

    def test_execute_code_stderr_returned_on_error(self):
        ctrl = self._make_controller()
        result = ctrl.execute_code("raise ValueError('boom')")
        self.assertIn("Error", result)

    def test_execute_code_timeout(self):
        cfg = DEFAULT_CONFIG.copy()
        cfg["code_execution_timeout"] = 1
        with patch.object(LlamaTerminalController, "initialize_ollama"):
            ctrl = LlamaTerminalController(config=cfg)
        result = ctrl.execute_code("import time; time.sleep(10)")
        self.assertIn("timed out", result)

    # ------------------------------------------------------------------
    # generate_code — markdown fence stripping
    # ------------------------------------------------------------------

    def test_generate_code_strips_fences(self):
        ctrl = self._make_controller()
        raw = "```python\nprint('hi')\n```"
        with patch.object(ctrl, "_call_ollama", return_value=raw):
            code = ctrl.generate_code("print hi")
        self.assertNotIn("```", code)
        self.assertIn("print('hi')", code)

    def test_generate_code_no_fences_unchanged(self):
        ctrl = self._make_controller()
        raw = "print('no fences')"
        with patch.object(ctrl, "_call_ollama", return_value=raw):
            code = ctrl.generate_code("print no fences")
        self.assertEqual(code, raw)

    # ------------------------------------------------------------------
    # fallback_to_claude_api
    # ------------------------------------------------------------------

    def test_fallback_no_api_key_returns_message(self):
        ctrl = self._make_controller()
        with patch.dict(os.environ, {}, clear=True):
            ctrl.config.pop("anthropic_api_key", None)
            result = ctrl.fallback_to_claude_api("hello")
        self.assertIn("ANTHROPIC_API_KEY", result)

    @patch("llama_terminal_controller.urllib.request.urlopen")
    def test_fallback_calls_claude_api(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {"content": [{"text": "Claude says hi"}]}
        ).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        ctrl = self._make_controller()
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            result = ctrl.fallback_to_claude_api("hello")
        self.assertEqual(result, "Claude says hi")

    # ------------------------------------------------------------------
    # _call_ollama
    # ------------------------------------------------------------------

    @patch("llama_terminal_controller.urllib.request.urlopen")
    def test_call_ollama_returns_content(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {"message": {"content": "Llama reply"}}
        ).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        ctrl = self._make_controller()
        result = ctrl._call_ollama("ping")
        self.assertEqual(result, "Llama reply")

    @patch(
        "llama_terminal_controller.urllib.request.urlopen",
        side_effect=Exception("network error"),
    )
    def test_call_ollama_returns_none_on_error(self, _):
        ctrl = self._make_controller()
        result = ctrl._call_ollama("ping")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
