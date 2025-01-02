# git2txt Exporter

This is a simple Python script that extracts all of the text in files from either a local directory or remote GitHub repository (by cloning) or a local directory. The script extracts the context of the files recursively and flattens them into a single file that is easy for ingestion into a LLM. 

## Features

### Automatic Dependency Management
- Installs all dependencies quietly on first run

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

For help, please check the GitHub issues page or open a new issue.
