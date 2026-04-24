"""CLI - Command line interface"""

from .parser   import build_parser, parse
from .executor import execute
from .errors   import CLIError
from .colors   import colorize, print_status

__all__ = [
    'build_parser', 'parse', 'execute',
    'CLIError', 'colorize', 'print_status',
    # legacy
    'handler', 'commands',
]
