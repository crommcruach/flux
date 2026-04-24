"""
ANSI color utilities for the Flux CLI.
Respects NO_COLOR env var and non-TTY output (pipes/files).
"""
import os
import sys


class _C:
    RED     = '\033[91m'
    GREEN   = '\033[92m'
    YELLOW  = '\033[93m'
    BLUE    = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN    = '\033[96m'
    WHITE   = '\033[97m'
    BOLD    = '\033[1m'
    DIM     = '\033[2m'
    RESET   = '\033[0m'


def _colors_enabled() -> bool:
    if os.getenv('NO_COLOR'):
        return False
    return sys.stdout.isatty()


def colorize(text: str, color: str = 'white', bold: bool = False) -> str:
    """Apply ANSI color to *text*. No-op when colours are disabled."""
    if not _colors_enabled():
        return str(text)
    code = getattr(_C, color.upper(), _C.WHITE)
    bold_code = _C.BOLD if bold else ''
    return f"{bold_code}{code}{text}{_C.RESET}"


def print_status(status: str, message: str) -> None:
    """Print a prefixed status line.

    status: 'success' | 'error' | 'warning' | 'info'
    """
    icons = {
        'success': colorize('✓', 'green'),
        'error':   colorize('✗', 'red'),
        'warning': colorize('⚠', 'yellow'),
        'info':    colorize('ℹ', 'cyan'),
    }
    icon = icons.get(status, colorize('•', 'white'))
    print(f"{icon} {message}")


def print_table(headers: list, rows: list) -> None:
    """Print a simple aligned table."""
    if not rows:
        print(colorize('(empty)', 'dim'))
        return

    col_widths = [len(str(h)) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))

    header_line = '  '.join(
        colorize(str(h).ljust(col_widths[i]), 'cyan', bold=True)
        for i, h in enumerate(headers)
    )
    print(header_line)
    print(colorize('─' * (sum(col_widths) + 2 * (len(headers) - 1)), 'dim'))

    for row in rows:
        print('  '.join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row)))
