"""
Session Management Package

Handles session state persistence and restoration.

Modules:
- session_persistence: File I/O operations
"""

from .session_persistence import SessionPersistence

__all__ = ['SessionPersistence']
