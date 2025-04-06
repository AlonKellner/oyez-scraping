# Concise LLM Agent Instructions

## Code Quality

- Write one small, testable component at a time; verify existing tests pass before continuing.
- Keep functions under 25 lines with single responsibility; use descriptive names.
- Add docstrings and type hints to all public functions and classes.
- Prefer simple solutions over complex ones.
- Document complex logic with clear comments.
- Use consistent naming patterns across similar components.
- Implement proper parameter validation at the beginning of functions.
- Add defensive programming techniques (e.g., handling division by zero).

## Error Handling

- Create custom exceptions for different error types; never silently ignore exceptions.
- Handle errors with proper context for debugging.
- Use exception chaining with `raise CustomError(...) from original_error`.
- Group error handling by type rather than having deeply nested try/except blocks.
- Ensure error messages include relevant context (file paths, parameter values, etc.).
- Implement robust retries with backoff for network operations.

## Testing

- Write tests before implementation; mock external dependencies appropriately.
- Use dependency injection to improve testability.
- Organize tests to match the code structure they're testing.
- Test changes with `pre-commit run --all-files` before committing.
- Separate unit tests from integration tests clearly.
- Test both normal operation and error handling paths.
- For numeric operations, allow for small differences using appropriate tolerances.
- Ensure file operations have proper cleanup in tests (use tempfile module).
- Add type hints to test fixtures and test methods.

## Development Workflow

- Refactor continuously; don't accumulate technical debt.
- Focus on making individual pieces work correctly before connecting them.
- Add packages with `uv add package-name`; remove with `uv remove package-name`.
- Add new files to git with the "Git add all" task.
- Format commit messages as `<type>: <sentence>` where type is "feat" or "fix".
- After committing, push changes with the "Git push" task.
- Update CHANGELOG.md with each significant change for better project tracking.
  - Add entries under relevant sections: Added, Changed, Fixed, Removed, etc.
  - Keep the Unreleased section at the top for changes not yet part of a release.
  - Reference the implemented component in the changelog entry (see CHANGELOG.md for examples).

## Environment & Architecture

- When updating environment, add changes to devcontainer configuration.
- Prioritize code correctness, testability, and maintainability over cleverness.
- Follow clear boundaries between architectural layers defined in design.md.
- Use consistent module structure within each architectural layer.
- Prefer composition over inheritance where possible.
- Create small, focused modules with clear responsibilities.
- Design for extensibility without premature abstraction.
