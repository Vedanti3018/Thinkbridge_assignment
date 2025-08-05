# Thinkbridge

A Python project using Poetry for dependency management.

## Installation

This project uses Poetry for dependency management. To get started:

1. Install Poetry (if not already installed):
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. Install dependencies:
   ```bash
   poetry install
   ```

3. Activate the virtual environment:
   ```bash
   poetry shell
   ```

## Development

- **Python version**: 3.9+
- **Dependencies**: See `pyproject.toml` for the complete list
- **Development tools**:
  - black (code formatting)
  - flake8 (linting)
  - isort (import sorting)
  - mypy (type checking)
  - pytest (testing)
  - pre-commit (git hooks)

### Development Setup

1. **Install pre-commit hooks** (already done):
   ```bash
   poetry run pre-commit install
   ```

2. **Run pre-commit on all files** (optional):
   ```bash
   poetry run pre-commit run --all-files
   ```

3. **Manual code quality checks**:
   ```bash
   # Format code
   poetry run black .

   # Sort imports
   poetry run isort .

   # Lint code
   poetry run flake8 .

   # Type checking
   poetry run mypy src/

   # Run tests
   poetry run pytest
   ```

## Usage

Run tests:
```bash
poetry run pytest
```

Format code:
```bash
poetry run black .
```

Lint code:
```bash
poetry run flake8 .
```

## Project Structure

```
thinkbridge/
├── pyproject.toml      # Poetry configuration
├── README.md          # This file
├── src/               # Source code
│   └── thinkbridge/
│       └── __init__.py
└── tests/             # Test files
    └── __init__.py
```
