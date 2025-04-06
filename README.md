# Oyez Scraping Project

A Python project demonstrating web scraping capabilities for [Oyez](https://www.oyez.org/), a multimedia archive of Supreme Court cases.

## Project Setup

This project uses:

- Python 3.10+
- `uv` for dependency management
- pre-commit hooks for code quality
- Docker support for containerized development

### Development Environment

1. Clone the repository
2. Ensure you have Docker installed
3. Open in VS Code with Dev Containers extension
4. The dev container will automatically:
   - Set up the Python environment
   - Install pre-commit hooks
   - Configure development tools

### Adding Dependencies

Use the VS Code task "Add uv dependency" to add new Python packages:

```sh
Command Palette (Ctrl/Cmd + Shift + P) > Tasks: Run Task > Add uv dependency
```

### Code Quality Tools

The project uses several code quality tools configured with pre-commit:

- Ruff for linting and formatting
- Pyright for type checking
- pytest for testing
- typos for spell checking

Run checks by committing.
