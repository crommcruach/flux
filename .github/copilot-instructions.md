# GitHub Copilot Instructions for Py_artnet

## Project Guidelines

**IMPORTANT**: Always read and follow the guidelines in [agent.md](../agent.md) at the root of this repository.

The agent.md file contains:
- Architecture principles and best practices
- Code organization standards
- State management rules (session_state.json vs config.json)
- Performance optimization guidelines
- Terminal safety rules for CLI application
- Git workflow (no auto-push!)
- Development workflow

## Quick Reference

### Before Starting Any Task:
1. ✅ Read [agent.md](../agent.md) for project guidelines
2. ✅ Check for existing code/modules before creating new ones
3. ✅ Ask before creating new API endpoints or classes
4. ✅ Verify which terminal is safe to use (CLI app running?)
5. ✅ Remember: session_state.json for ALL data, config.json for globals only

### Key Principles:
- **CLI Application**: Backend is a command-line application
- **Performance First**: Low latency is top priority
- **Local Application**: No auth, no security overhead
- **State Management**: All session + live data → session_state.json
- **Terminal Safety**: Never send commands to terminal where app runs
- **Git**: Never auto-push, only local commits
- **Code Reuse**: Always search for existing implementations first

## For Every New Chat Session

Start by reviewing [agent.md](../agent.md) to understand the project structure, conventions, and requirements.
