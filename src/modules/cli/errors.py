"""
CLI error types for the Flux CLI.
"""
from .colors import colorize


class CLIError(Exception):
    """User-facing CLI error with an optional suggestion and examples."""

    def __init__(self, message: str, suggestion: str = '', examples: list = None):
        self.message = message
        self.suggestion = suggestion
        self.examples = examples or []
        super().__init__(message)

    def display(self) -> None:
        """Print a formatted error block to stdout."""
        print(f"\n{colorize('Error:', 'red', bold=True)} {self.message}\n")
        if self.suggestion:
            print(f"{colorize('Suggestion:', 'yellow')} {self.suggestion}\n")
        if self.examples:
            print(colorize('Examples:', 'cyan'))
            for ex in self.examples:
                if ex and not ex.startswith('#'):
                    print(f"  {colorize('$', 'green')} flux {ex}")
                elif ex:
                    print(f"  {colorize(ex, 'dim')}")
            print()
