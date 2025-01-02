# git2txt Exporter

A Python script that exports text files from either a remote GitHub repository (by cloning) or a local directory. Perfect for archiving code, creating documentation, or simply having a consolidated view of text-based files in your project.

## Features

### Automatic Dependency Management
- Installs GitPython automatically if not present
- Handles all dependencies quietly with a single status message

### Flexible Input Sources
- Remote GitHub repositories (public or private)
- Local Git repositories (with commit history)
- Local directories (non-Git)

### Smart URL Parsing
- Handles various GitHub URL formats:
  - Basic repository URLs (`https://github.com/owner/repo`)
  - Git URLs (`https://github.com/owner/repo.git`)
  - Tree URLs (`https://github.com/owner/repo/tree/branch`)
- Automatically extracts branch information from tree URLs

### Intelligent File Processing
- Detects text files using MIME types and extensions
- Skips binary files, test files, and hidden files automatically
- Preserves directory structure in output
- Captures Git commit history when available

### Organized Output
- Creates a single consolidated text file with:
  - Directory structure visualization
  - File contents with clear separators
  - Git commit information (when available)
  - File statistics (characters, lines, tokens)
- Exports stored in `exports/` directory
- Logs written to `logs/` directory
- Both directories automatically excluded from Git

### Security & Authentication
- Supports GitHub Personal Access Tokens for private repositories
- Masks tokens in logs for security
- Uses HTTPS for authenticated requests

### Error Handling & Logging
- Comprehensive error messages
- Detailed logging with timestamps
- Both console and file logging

## Installation

1. Clone the repository (for development or personal usage):
```bash
git clone https://github.com/michaeljabbour/git2txt.git
cd git2txt
```

2. (Optional) Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # or .\venv\Scripts\activate on Windows
```

3. (Optional) Run tests:
```bash
pytest tests/
```

If you'd like, you can view coverage as well:
```bash
pytest tests/ --cov=git2txt
```

## Quick Start Usage

You can run `git2txt.py` directly without installing anything else, as the script handles dependencies automatically. Below are common usage patterns:

### 1. Export From a Remote GitHub Repo

Basic usage:
```bash
python git2txt.py --repo-url https://github.com/owner/repo.git
```

Optional: Specify a branch or commit:
```bash
python git2txt.py --repo-url https://github.com/owner/repo.git --branch dev
```

Private Repos: Provide your Personal Access Token:
```bash
python git2txt.py --repo-url https://github.com/owner/private-repo.git --token YOUR_TOKEN
```

Skip Removing the Clone: Keep the cloned repo after export (for debugging):
```bash
python git2txt.py --repo-url https://github.com/owner/repo.git --skip-remove
```

### 2. Export From a Local Directory

```bash
python git2txt.py --local-dir /path/to/local/project
```

- If the directory contains a `.git` folder, git2txt will attempt to gather commit info for each file
- If not, it still processes files but omits commit data

### 3. Custom Output Filename

```bash
python git2txt.py --repo-url https://github.com/owner/repo.git --output-file my_export.txt
```

This places the file in `exports/my_export.txt`.

## Development

After cloning, you can edit `git2txt.py` or the supporting modules. We recommend using a virtual environment and the pytest library for testing.

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=git2txt

# Run a specific test file
pytest tests/test_git2txt.py
```

## Troubleshooting

### Common Issues

1. Git Not Found
```
Error: Git is not installed or not in PATH
```
Solution: Install Git and ensure your system PATH includes it.

2. Permission Denied
```
PermissionError: [Errno 13] Permission denied: 'exports'
```
Solution: Run the script in a directory where you have write permissions, or adjust permissions on the `exports/` folder.

3. Network Issues
```
fatal: unable to access: Connection refused
```
Solution: Check your internet connection, firewall settings, or verify the repository URL.

For more issues or help, please check the GitHub issues page or open a new ticket.

## License

This project is licensed under the MIT License.
