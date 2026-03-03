# Development Tools

This directory contains development and maintenance tools for the Py_artnet project.

## Tools

### sync_cli_api.py

Ensures consistency between API endpoints and CLI commands.

**Features:**
- Discovers all API endpoints automatically
- Checks if each endpoint has a corresponding CLI command
- Generates reports of missing mappings
- Creates CLI command stubs for new endpoints
- Exports JSON reports for CI/CD

**Usage:**

```bash
# Check for missing CLI mappings
python tools/sync_cli_api.py --check

# Generate detailed report
python tools/sync_cli_api.py --report

# Generate CLI command stubs
python tools/sync_cli_api.py --generate-stubs > new_commands.py

# Export JSON report
python tools/sync_cli_api.py --check --export-json report.json
```

**Integration:**

See [docs/CLI_REDESIGN.md](../docs/CLI_REDESIGN.md) for:
- Pre-commit hook setup
- CI/CD integration
- Developer checklist
- Maintenance guidelines

## Adding New Tools

When adding new tools to this directory:

1. Create a descriptive filename (e.g., `check_something.py`)
2. Add shebang line: `#!/usr/bin/env python3`
3. Include docstring with usage examples
4. Make it executable: `chmod +x tools/your_tool.py`
5. Update this README with tool description
6. Add to `.gitignore` if it generates temporary files
