#!/usr/bin/env python3
"""Entry-point script for the Llama Smart Terminal Controller.

The full implementation lives in ``llama_terminal_controller.py`` so that it
can be imported by tests and other modules.  This file simply launches the
interactive terminal when executed directly.
"""

from llama_terminal_controller import LlamaTerminalController

if __name__ == "__main__":
    controller = LlamaTerminalController()
    controller.run_terminal()
