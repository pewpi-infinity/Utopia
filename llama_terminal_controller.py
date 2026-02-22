#!/usr/bin/env python3
"""
Llama-powered Smart Terminal Controller

Features:
- Auto-starts Ollama daemon as background service
- Preloads Llama model on startup (cached for instant access)
- Natural language CLI with full conversation history
- Real code generation and execution
- File access and modification across multiple repositories
- Claude API fallback for complex reasoning
- Production-ready error handling and logging
"""

import os
import sys
import json
import time
import shutil
import logging
import subprocess
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
LOG_DIR = os.path.expanduser("~/.llama-terminal")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(LOG_DIR, "terminal.log")),
    ],
)
logger = logging.getLogger("LlamaTerminal")

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_CONFIG: Dict[str, Any] = {
    "ollama_host": "http://localhost:11434",
    "default_model": "llama3.2",
    "fallback_model": "llama3.1",
    "claude_model": "claude-3-5-sonnet-20241022",
    "max_conversation_history": 20,
    "code_execution_timeout": 30,
    "log_level": "INFO",
    "repositories": {
        "utopia": "~/repos/utopia",
        "joe": "~/repos/joe",
        "infinity": "~/repos/infinity",
        "vectors": "~/repos/vectors",
    },
    "model_cache_dir": "~/.ollama",
}


# ---------------------------------------------------------------------------
# Ollama daemon manager
# ---------------------------------------------------------------------------
class OllamaManager:
    """Manages the Ollama daemon lifecycle and model caching."""

    def __init__(self, config: Dict):
        self.config = config
        self.host = config.get("ollama_host", DEFAULT_CONFIG["ollama_host"])
        self._process: Optional[subprocess.Popen] = None

    def is_running(self) -> bool:
        """Return True if the Ollama HTTP API is reachable."""
        try:
            req = urllib.request.Request(f"{self.host}/api/tags")
            with urllib.request.urlopen(req, timeout=2) as resp:
                return resp.status == 200
        except Exception:
            return False

    def start(self) -> bool:
        """Start the Ollama daemon if it is not already running."""
        if self.is_running():
            logger.info("Ollama daemon is already running")
            return True

        logger.info("Starting Ollama daemon...")
        ollama_bin = self._find_ollama_binary()
        if not ollama_bin:
            logger.warning("Ollama not found in PATH; attempting install...")
            if not self._install_ollama():
                return False
            ollama_bin = self._find_ollama_binary()
            if not ollama_bin:
                logger.error("Ollama binary not found after install")
                return False

        try:
            self._process = subprocess.Popen(
                [ollama_bin, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            # Wait up to 15 s for the daemon to start
            for _ in range(30):
                time.sleep(0.5)
                if self.is_running():
                    logger.info("Ollama daemon started successfully")
                    return True
            logger.error("Ollama daemon failed to start within timeout")
            return False
        except Exception as e:
            logger.error(f"Failed to start Ollama: {e}")
            return False

    def stop(self):
        """Stop the Ollama daemon if we started it."""
        if self._process and self._process.poll() is None:
            logger.info("Stopping Ollama daemon...")
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()

    def preload_model(self, model: str) -> bool:
        """Ensure *model* is downloaded and cached locally."""
        if self._model_exists(model):
            logger.info(f"Model '{model}' already cached")
            return True

        logger.info(f"Pulling model '{model}'… (this may take a while)")
        ollama_bin = self._find_ollama_binary()
        if not ollama_bin:
            return False
        try:
            result = subprocess.run(
                [ollama_bin, "pull", model],
                timeout=600,
            )
            if result.returncode == 0:
                logger.info(f"Model '{model}' cached successfully")
                return True
            logger.warning(f"Failed to pull model '{model}'")
            return False
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout pulling model '{model}'")
            return False
        except Exception as e:
            logger.error(f"Error pulling model '{model}': {e}")
            return False

    def _model_exists(self, model: str) -> bool:
        """Return True if *model* is already in the local Ollama library."""
        try:
            req = urllib.request.Request(f"{self.host}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            return any(model in m["name"] for m in data.get("models", []))
        except Exception:
            return False

    @staticmethod
    def _find_ollama_binary() -> Optional[str]:
        return shutil.which("ollama")

    @staticmethod
    def _install_ollama() -> bool:
        """Install Ollama via the official install script."""
        logger.info("Installing Ollama via official install script…")
        try:
            result = subprocess.run(
                "curl -fsSL https://ollama.ai/install.sh | sh",
                shell=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                logger.info("Ollama installed successfully")
                return True
            logger.error(f"Ollama install failed: {result.stderr}")
            return False
        except Exception as e:
            logger.error(f"Error installing Ollama: {e}")
            return False


# ---------------------------------------------------------------------------
# Repository manager
# ---------------------------------------------------------------------------
class RepositoryManager:
    """Provides read/write access to multiple local repositories."""

    def __init__(self, repos: Dict[str, str]):
        self.repos = {
            name: os.path.expanduser(path) for name, path in repos.items()
        }

    def get_repo_path(self, repo_name: str) -> Optional[str]:
        return self.repos.get(repo_name)

    def read_file(self, repo_name: str, file_path: str) -> Optional[str]:
        """Return the content of *file_path* inside *repo_name*, or None."""
        repo_path = self.get_repo_path(repo_name)
        if not repo_path:
            logger.error(f"Unknown repository: {repo_name}")
            return None
        full_path = os.path.join(repo_path, file_path)
        if not os.path.exists(full_path):
            logger.error(f"File not found: {full_path}")
            return None
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading {full_path}: {e}")
            return None

    def write_file(self, repo_name: str, file_path: str, content: str) -> bool:
        """Write *content* to *file_path* inside *repo_name*."""
        repo_path = self.get_repo_path(repo_name)
        if not repo_path:
            logger.error(f"Unknown repository: {repo_name}")
            return False
        full_path = os.path.join(repo_path, file_path)
        os.makedirs(os.path.dirname(full_path) or repo_path, exist_ok=True)
        try:
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"Written to {full_path}")
            return True
        except Exception as e:
            logger.error(f"Error writing {full_path}: {e}")
            return False

    def list_files(self, repo_name: str, subdir: str = "") -> List[str]:
        """Return sorted relative paths of all files under *subdir* in *repo_name*."""
        repo_path = self.get_repo_path(repo_name)
        if not repo_path:
            return []
        target = os.path.join(repo_path, subdir) if subdir else repo_path
        if not os.path.exists(target):
            return []
        files = []
        for root, _, filenames in os.walk(target):
            for filename in filenames:
                rel = os.path.relpath(os.path.join(root, filename), repo_path)
                files.append(rel)
        return sorted(files)


# ---------------------------------------------------------------------------
# Main controller
# ---------------------------------------------------------------------------
class LlamaTerminalController:
    """
    Smart terminal controller powered by Llama via Ollama.

    Responsibilities:
    - Auto-start Ollama daemon and preload configured model
    - Maintain conversation history for contextual replies
    - Generate and execute real Python code on request
    - Access / modify files across multiple repos
    - Fall back to Claude API when Ollama is unavailable
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or self._load_config()
        self._configure_logging()
        self.conversation_history: List[Dict[str, str]] = []
        self.ollama = OllamaManager(self.config)
        self.repo_manager = RepositoryManager(
            self.config.get("repositories", DEFAULT_CONFIG["repositories"])
        )
        self.initialize_ollama()

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_config() -> Dict:
        config_paths = [
            "terminal_controller_config.json",
            os.path.expanduser("~/.llama-terminal/config.json"),
        ]
        for path in config_paths:
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        user_cfg = json.load(f)
                    cfg = DEFAULT_CONFIG.copy()
                    cfg.update(user_cfg)
                    return cfg
                except Exception as e:
                    logger.warning(f"Failed to load config from {path}: {e}")
        return DEFAULT_CONFIG.copy()

    def _configure_logging(self):
        level_name = self.config.get("log_level", "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)
        logging.getLogger().setLevel(level)

    # ------------------------------------------------------------------
    # Ollama lifecycle
    # ------------------------------------------------------------------

    def initialize_ollama(self):
        """Start the Ollama daemon and preload the configured model."""
        if not self.ollama.start():
            logger.warning(
                "Could not start Ollama daemon; responses will use Claude fallback"
            )
            return
        model = self.config.get("default_model", DEFAULT_CONFIG["default_model"])
        self.ollama.preload_model(model)
        logger.info("Ollama/Llama initialized.")

    # ------------------------------------------------------------------
    # Ollama API
    # ------------------------------------------------------------------

    def _call_ollama(
        self, prompt: str, system: Optional[str] = None
    ) -> Optional[str]:
        """Send *prompt* to Ollama (with conversation context) and return the reply."""
        model = self.config.get("default_model", DEFAULT_CONFIG["default_model"])
        host = self.config.get("ollama_host", DEFAULT_CONFIG["ollama_host"])

        messages: List[Dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.extend(self.conversation_history)
        messages.append({"role": "user", "content": prompt})

        payload = json.dumps(
            {"model": model, "messages": messages, "stream": False}
        ).encode("utf-8")

        try:
            req = urllib.request.Request(
                f"{host}/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
            return data.get("message", {}).get("content", "")
        except urllib.error.URLError as e:
            logger.error(f"Ollama API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error calling Ollama: {e}")
            return None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def parse_input(self, user_input: str) -> str:
        """Use Llama to analyse and clarify the user's intent."""
        system = (
            "You are a smart terminal assistant. "
            "Analyse the user's request and identify its intent: "
            "code_generation, file_access, system_command, or conversation. "
            "Return the request reformulated clearly in one or two sentences."
        )
        result = self._call_ollama(user_input, system=system)
        return result if result else user_input

    def generate_code(self, parsed_input: str) -> str:
        """Ask Llama to produce executable Python 3 code for *parsed_input*."""
        system = (
            "You are a Python 3 code generator. "
            "Output only executable Python code — no markdown fences, no explanation. "
            "Use only the standard library unless the user explicitly asks otherwise."
        )
        code = self._call_ollama(parsed_input, system=system)
        if not code:
            return "# Could not generate code"
        # Strip accidental markdown code fences
        code = code.strip()
        if code.startswith("```"):
            lines = code.split("\n")
            end = -1 if lines[-1].strip() == "```" else len(lines)
            code = "\n".join(lines[1:end])
        return code

    def execute_code(self, code: str) -> Optional[str]:
        """Execute *code* as a Python subprocess with a configurable timeout."""
        timeout = self.config.get(
            "code_execution_timeout", DEFAULT_CONFIG["code_execution_timeout"]
        )
        try:
            result = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode == 0:
                return result.stdout
            logger.error(f"Code execution stderr: {result.stderr}")
            return f"Error: {result.stderr}"
        except subprocess.TimeoutExpired:
            logger.error("Code execution timed out")
            return "Error: execution timed out"
        except Exception as e:
            logger.error(f"Error executing code: {e}")
            return None

    def access_repository(
        self, repo_name: str, action: str = "list", **kwargs
    ) -> Any:
        """
        Interact with a named repository.

        action='list'  → list files (optional kwarg: subdir)
        action='read'  → read a file (required kwarg: file_path)
        action='write' → write a file (required kwargs: file_path, content)
        """
        if action == "list":
            return self.repo_manager.list_files(
                repo_name, kwargs.get("subdir", "")
            )
        if action == "read":
            return self.repo_manager.read_file(repo_name, kwargs["file_path"])
        if action == "write":
            return self.repo_manager.write_file(
                repo_name, kwargs["file_path"], kwargs["content"]
            )
        logger.error(f"Unknown repository action: {action}")
        return None

    def manage_files(
        self, file_path: str, action: str = "read", content: str = ""
    ) -> Any:
        """Read, write, or list files at an arbitrary path."""
        full_path = os.path.expanduser(file_path)
        try:
            if action == "read":
                with open(full_path, "r", encoding="utf-8") as f:
                    return f.read()
            if action == "write":
                parent = os.path.dirname(full_path)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)
                return True
            if action == "list":
                if os.path.isdir(full_path):
                    return os.listdir(full_path)
                return []
        except Exception as e:
            logger.error(f"File operation '{action}' on '{file_path}' failed: {e}")
        return None

    def fallback_to_claude_api(self, user_input: str) -> Optional[str]:
        """Call the Anthropic Claude API as a fallback for complex reasoning."""
        api_key = os.environ.get("ANTHROPIC_API_KEY") or self.config.get(
            "anthropic_api_key"
        )
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY not set; Claude fallback unavailable")
            return (
                "Claude API key not configured. "
                "Set the ANTHROPIC_API_KEY environment variable."
            )

        claude_model = self.config.get(
            "claude_model", DEFAULT_CONFIG["claude_model"]
        )
        messages = [
            {"role": m["role"], "content": m["content"]}
            for m in self.conversation_history
            if m["role"] in ("user", "assistant")
        ]
        messages.append({"role": "user", "content": user_input})

        payload = json.dumps(
            {"model": claude_model, "max_tokens": 4096, "messages": messages}
        ).encode("utf-8")

        try:
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
            content_blocks = data.get("content", [])
            if content_blocks and isinstance(content_blocks, list):
                return content_blocks[0].get("text", "")
            return ""
        except urllib.error.HTTPError as e:
            logger.error(f"Claude API HTTP {e.code}: {e.read().decode()}")
            return None
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return None

    # ------------------------------------------------------------------
    # Conversation history
    # ------------------------------------------------------------------

    def _update_conversation_history(self, role: str, content: str):
        self.conversation_history.append({"role": role, "content": content})
        max_hist = self.config.get(
            "max_conversation_history",
            DEFAULT_CONFIG["max_conversation_history"],
        )
        if len(self.conversation_history) > max_hist:
            self.conversation_history = self.conversation_history[-max_hist:]

    # ------------------------------------------------------------------
    # Built-in CLI commands
    # ------------------------------------------------------------------

    def _handle_special_commands(self, user_input: str) -> Optional[str]:
        """Return a response string for built-in commands, or None if not matched."""
        cmd = user_input.strip().lower()

        if cmd in ("exit", "quit", "bye"):
            raise KeyboardInterrupt

        if cmd == "help":
            return (
                "Built-in commands:\n"
                "  help                      Show this help\n"
                "  history                   Show conversation history\n"
                "  repo <name> [subdir]      List files in a repository\n"
                "  read <repo> <file>        Read a file from a repository\n"
                "  exit / quit / bye         Exit the terminal\n"
                "\nOr just type naturally — Llama will understand!"
            )

        if cmd == "history":
            if not self.conversation_history:
                return "(no history yet)"
            return "\n".join(
                f"[{m['role']}]: {m['content'][:80]}"
                for m in self.conversation_history
            )

        if cmd.startswith("repo "):
            parts = user_input.split(maxsplit=2)
            repo_name = parts[1]
            subdir = parts[2] if len(parts) > 2 else ""
            files = self.access_repository(repo_name, action="list", subdir=subdir)
            if files:
                return "\n".join(files)
            return f"No files found in repo '{repo_name}'"

        if cmd.startswith("read "):
            parts = user_input.split(maxsplit=2)
            if len(parts) == 3:
                repo_name, file_path = parts[1], parts[2]
                content = self.access_repository(
                    repo_name, action="read", file_path=file_path
                )
                return content or f"Could not read '{file_path}' from '{repo_name}'"

        return None

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run_terminal(self):
        """Start the interactive terminal loop."""
        print("=" * 60)
        print("  Llama Smart Terminal Controller")
        print("  Type 'help' for commands, 'exit' to quit")
        print("=" * 60)
        try:
            while True:
                try:
                    user_input = input("\n> ").strip()
                except EOFError:
                    break

                if not user_input:
                    continue

                # Built-in commands take priority
                special = self._handle_special_commands(user_input)
                if special is not None:
                    print(special)
                    continue

                # Add user turn to history
                self._update_conversation_history("user", user_input)

                # Try Llama via Ollama
                response = self._call_ollama(user_input)
                if response:
                    print(f"\n{response}")
                    self._update_conversation_history("assistant", response)
                else:
                    # Fall back to Claude
                    logger.info("Ollama unavailable — falling back to Claude API")
                    fallback = self.fallback_to_claude_api(user_input)
                    if fallback:
                        print(f"\n[Claude] {fallback}")
                        self._update_conversation_history("assistant", fallback)
                    else:
                        print(
                            "\nUnable to process your request right now. "
                            "Check that Ollama is running and the model is loaded."
                        )
        except KeyboardInterrupt:
            pass
        finally:
            print("\nGoodbye!")
            logger.info("Terminal controller terminated by user")


if __name__ == "__main__":
    controller = LlamaTerminalController()
    controller.run_terminal()