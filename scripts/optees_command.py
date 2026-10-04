"""Locate the Optees MCP server without machine-specific paths in configs."""

import os
import shutil
import sys
from pathlib import Path


def optees_command(config=None):
    """OPTEES_COMMAND, then config 'optees_command', then optees-mcp next to this Python, then PATH."""
    explicit = os.environ.get('OPTEES_COMMAND') or (config or {}).get('optees_command')
    if explicit:
        return explicit
    sibling = Path(sys.executable).parent / 'optees-mcp'
    if sibling.exists():
        return str(sibling)
    found = shutil.which('optees-mcp')
    if found:
        return found
    raise RuntimeError('optees-mcp non trovato: impostare OPTEES_COMMAND o installarlo nel Python in uso')
