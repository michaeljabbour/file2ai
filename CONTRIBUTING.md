# Contributing to git2txt

Thank you for your interest in contributing to git2txt! This document provides guidelines and instructions for contributing to the project.

## Development Setup

1. Clone the repository:
```bash
git clone https://github.com/michaeljabbour/git2txt.git
cd git2txt
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # or .\venv\Scripts\activate on Windows
```

3. Install development dependencies:
```bash
pip install -e ".[test]"  # Installs the package in editable mode with test dependencies
```

## Code Style

We use Black for code formatting to maintain consistent style. Before submitting a pull request:

1. Install Black:
```bash
pip install black
```

2. Format your code:
```bash
black .
```

The project is configured with Black settings in `pyproject.toml`, including:
- Line length: 100 characters
- Python 3.7+ compatibility

## Testing

We use pytest for testing. To run the tests:

1. Install test dependencies (if you haven't already):
```bash
pip install -e ".[test]"
```

2. Run the tests:
```bash
pytest
```

Make sure to add tests for any new functionality you implement.

## Submitting Pull Requests

1. Fork the repository and create your branch from `main`:
```bash
git checkout -b feature/your-feature-name
```

2. Make your changes and ensure:
   - Code is formatted with Black
   - Tests pass
   - Documentation is updated if needed

3. Commit your changes:
```bash
git add .
git commit -m "feat: description of your changes"
```

4. Push to your fork and submit a pull request:
```bash
git push origin feature/your-feature-name
```

5. In your pull request description:
   - Clearly describe the problem and solution
   - Include the relevant issue number if applicable
   - Note any breaking changes

## Questions or Issues?

If you have questions or run into issues, please:
1. Check existing issues to see if it's already been addressed
2. Open a new issue with a clear description and reproduction steps
