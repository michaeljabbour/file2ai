# git2txt Exporter

A Python script that clones a (public or private) GitHub repository, checks out a specified branch, and exports relevant **text files** to a single text document. It excludes:

- Hidden files and directories.
- Files or directories containing "test" in their names.
- Non-text files (based on MIME type).
- Anything in `.git`.

This keeps the export focused on the main application code rather than tests or binaries.

## Features

1. **Automatic GitPython Install**  
   If GitPython is not found, the script installs it automatically.

2. **Branch Detection**  
   - Automatically parses standard GitHub URLs, even if they include `/tree/<branch>`.
   - If you provide a separate branch or commit via the `--branch` argument, it will switch to that branch after cloning.

3. **Optional Authentication**  
   Use `--token <YOUR_TOKEN>` for private repositories. The script will inject the token into the clone URL for HTTPS.

4. **Automatic Cleanup**  
   By default, the repository is cloned into a temporary directory and removed after export.  
   Use `--skip-remove` to keep the cloned files for debugging or further inspection.

5. **Prompting for Repo URL**  
   If `--repo-url` is omitted, you’ll be prompted interactively.

## Installation

1. **Clone or Download** this project.  
2. **Install** Python 3.7 or higher (any recent version works).  
3. **Make** the script executable:
   ```bash
   chmod +x git2txt.py
