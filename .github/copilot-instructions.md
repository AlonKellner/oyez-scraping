# Dependencies

Use the `uv add ${some-package} --link-mode=copy` shell command to add dependencies to the project (in the pyproject.toml).  
Use the `uv remove ${some-package}` shell command to remove dependencies from the project (in the pyproject.toml).

# Code generation Guidelines

Use the `Pre-Commit All` and `Pre-commit Current` tasks to sync the venv, apply formatting, run tests and to check yourself.  
After every feature implementation test yourself using pytest tests in the `tests` directory, run the tests with the `Pre-Commit All` command.

# Git

Use the `Git add all` task after creating new files to add them to the `pre-commit` context.  
After making significant changes - commit them.  
Commit messages must follow the pattern "<type>: <sentence>\n[<details>]", where the <type> is one of [feat, fix], the <sentence> is no more than 60 characters and the <details> are optional.  
Use the `Git push` task after every successful commit on an existing branch.
