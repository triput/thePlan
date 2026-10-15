# ==============================================================================
#  File: apps/cli/theplan/safe_help.py
#  Description: Argparse help that survives narrow console encodings (DEF-046).
#  Component: CLI
#  Version: 1.0
#  Created: 2026-10-14
#  Last Update: 2026-10-14
# ==============================================================================

"""Shared help writer for Windows cp1252 (and other narrow encodings).

UTF-8 consoles keep original Unicode. On encode failure, map common glyphs to
ASCII then fall back to replacement — do not require PYTHONIOENCODING.
"""

from __future__ import annotations

import argparse
import sys
from typing import TextIO

# Readable ASCII stand-ins for glyphs that break cp1252 help (arrows, dashes, …).
_HELP_ASCII_FALLBACKS = str.maketrans(
    {
        "\u2192": "->",  # →
        "\u2190": "<-",  # ←
        "\u2194": "<->",  # ↔
        "\u21d2": "=>",  # ⇒
        "\u2014": "-",  # —
        "\u2013": "-",  # –
        "\u2026": "...",  # …
    }
)

_installed = False


def write_help_text(message: str, file: TextIO | None = None) -> None:
    """Write help/usage text without raising UnicodeEncodeError on narrow encodings."""
    if not message:
        return
    stream = sys.stderr if file is None else file
    try:
        stream.write(message)
        return
    except UnicodeEncodeError:
        pass

    narrowed = message.translate(_HELP_ASCII_FALLBACKS)
    try:
        stream.write(narrowed)
        return
    except UnicodeEncodeError:
        encoding = getattr(stream, "encoding", None) or "ascii"
        stream.write(narrowed.encode(encoding, errors="replace").decode(encoding))


def install_safe_argparse_help() -> None:
    """Patch ArgumentParser._print_message once so all nested help is covered."""
    global _installed
    if _installed:
        return

    def _print_message(self: argparse.ArgumentParser, message: str, file: TextIO | None = None) -> None:
        write_help_text(message, file)

    argparse.ArgumentParser._print_message = _print_message  # type: ignore[method-assign]
    _installed = True
