# Chat guidelines

When running vscode tasks in quick succession please don't explain them or your process until you finished running them all, and even when all tasks end please be concise with your explanations.

# Dependencies

Use the `uv add ${some-package}` shell command to add dependencies to the project (in the pyproject.toml).  
Use the `uv remove ${some-package}` shell command to remove dependencies from the project (in the pyproject.toml).

# Code generation Guidelines

Use the `pre-commit run --all-files` command to sync the venv, apply formatting, run tests and to check yourself.  
After every feature implementation test yourself using pytest tests in the `tests` directory, run all tests at once with the `pre-commit run --all-files` command.

## Development Principles

1. **Incremental Development**:

   - Implement one small, testable component at a time
   - Verify that existing tests pass before moving on
   - Focus on having a working end-to-end flow, even with limited functionality

2. **Clean Code Practices**:

   - Follow the Single Responsibility Principle - each function should do one thing well
   - Keep functions under 25 lines whenever possible
   - Use meaningful and descriptive names for functions, classes, and variables
   - Add proper docstrings and type hints to all public functions and classes

3. **Error Handling**:

   - Create appropriate custom exceptions for different error scenarios
   - Implement proper retries with backoff for network operations
   - Add contextual information to error messages to aid debugging
   - Never silently ignore exceptions without logging or handling

4. **Refactoring**:
   - Refactor as you go rather than accumulating technical debt
   - When adding new functionality, first refactor existing code if needed
   - Follow the "boy scout rule": Leave the code cleaner than you found it
   - Maintain test coverage during refactoring

## Implementation Workflow

For each feature implementation:

1. **Plan**: Define scope and identify modules to modify before writing code
2. **Test**: Write tests before implementation when possible
3. **Implement**: Write clean, focused code with proper error handling
4. **Validate**: Verify functionality with tests and manual checks
5. **Refactor**: Clean up the implementation and eliminate code smells
6. **Document**: Add appropriate documentation and comments

# Git

Use the `Git add all` task after creating new files to add them to the `pre-commit` context.  
After making significant changes, run the `pre-commit run --all-files` command, then `Git add all` if there are any changes, and then commit them.  
Commit messages must follow the pattern "<type>: <sentence>\n[<details>]", where the <type> is one of [feat, fix], the <sentence> is no more than 60 characters and the <details> are optional.  
Use the `Git push` task after every successful commit on an existing branch.

# Testing Best Practices

1. **Test Structure**:

   - Organize tests to match the code structure
   - Separate unit, integration, and end-to-end tests
   - Use parametrized tests for checking multiple similar cases

2. **Mocking**:
   - Mock external dependencies appropriately in unit tests
   - Use dependency injection to facilitate testing
   - Test edge cases and error conditions thoroughly

# Documentation

1. **Code Documentation**:

   - Add docstrings to all public functions and classes explaining:
     - What the function does
     - Parameters and their purpose
     - Return values
     - Exceptions that might be raised
   - Include examples for complex operations
   - Add comments for complex or non-obvious logic

2. **Project Documentation**:
   - Update README with new features and usage examples
   - Document design decisions and architecture choices
   - Include examples of common usage patterns

# Environment

Since this is a devcontainer, when making changes to the environment please make sure to add the new installations and setup to an automated script or a persistent tool, such as the devcontainer dockerfile, or using the `uv add/remove` shell commands etc.
This dev container includes the Docker CLI (`docker`) pre-installed and available on the `PATH` for running and managing containers using the Docker daemon on the host machine.

# Decision-Making Principles

When making design or implementation decisions, prioritize:

1. **Correctness**: The code must work correctly and handle edge cases
2. **Testability**: Design for testability from the beginning
3. **Maintainability**: Write code that's easy to understand and modify
4. **Simplicity**: Prefer simple solutions over complex ones
5. **Performance**: Consider performance implications, especially for data-intensive operations
