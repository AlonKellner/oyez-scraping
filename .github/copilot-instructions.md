# Concise LLM Agent Instructions

## Code Quality
- Write one small, testable component at a time; verify existing tests pass before continuing.
- Keep functions under 25 lines with single responsibility; use descriptive names.
- Add docstrings and type hints to all public functions and classes.
- Prefer simple solutions over complex ones.
- Document complex logic with clear comments.

## Error Handling
- Create custom exceptions for different error types; never silently ignore exceptions.
- Handle errors with proper context for debugging.
- Implement robust retries with backoff for network operations.

## Testing
- Write tests before implementation; mock external dependencies appropriately.
- Use dependency injection to improve testability.
- Organize tests to match the code structure they're testing.
- Test changes with `pre-commit run --all-files` before committing.

## Development Workflow
- Refactor continuously; don't accumulate technical debt.
- Focus on making individual pieces work correctly before connecting them.
- Add packages with `uv add package-name`; remove with `uv remove package-name`.
- Add new files to git with the "Git add all" task.
- Format commit messages as `<type>: <sentence>` where type is "feat" or "fix".
- After committing, push changes with the "Git push" task.

## Environment & Architecture
- When updating environment, add changes to devcontainer configuration.
- Prioritize code correctness, testability, and maintainability over cleverness.
