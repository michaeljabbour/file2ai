#!/usr/bin/env python3
"""
git2txt Exporter

Clones a GitHub repository (public or private), optionally checking out a branch,
and exports text files to a single text file in an 'exports/' directory. It excludes:
  - Hidden files/directories
  - Anything with "test" in its name
  - Non-text/binary files (based on MIME type)
  - .git folder

If --repo-url is not provided, the script will prompt the user.

Handles sub-URLs like:
  https://github.com/owner/repo/tree/<branch>/<subdir>
by automatically parsing out the branch and ignoring the subdir portion.

Example usage:
  python git2txt.py --repo-url https://github.com/owner/repo.git
  python git2txt.py --repo-url https://github.com/owner/repo/tree/dev/docs
  python git2txt.py --repo-url https://github.com/owner/private-repo.git --token your_token
"""

import os
import sys
import subprocess
import argparse
import tempfile
import logging
import mimetypes
from pathlib import Path
import re

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

def install_gitpython_quietly():
    """
    Installs GitPython automatically if not present, using pip in quiet mode,
    and shows a single "Installing dependencies..." message.
    """
    logging.info("Installing dependencies... (this may take a moment)")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "gitpython", "--quiet"],
        check=True
    )

def ensure_gitpython():
    """
    Check if GitPython is available; if not, install it quietly.
    """
    try:
        import git  # noqa
    except ImportError:
        install_gitpython_quietly()

# Ensure GitPython is available
ensure_gitpython()
from git import Repo, exc  # now safe to import

def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments. If --repo-url is not provided,
    we will prompt the user for one.
    """
    parser = argparse.ArgumentParser(
        description="Clone a GitHub repo and export main code files into a single text file."
    )
    parser.add_argument(
        "--repo-url", 
        help="GitHub URL, e.g. https://github.com/owner/repo.git or /tree/<branch> sub-URL."
    )
    parser.add_argument(
        "--branch", 
        default=None, 
        help="Branch or commit to checkout (overrides extracted branch from URL)."
    )
    parser.add_argument(
        "--token", 
        default=None, 
        help="GitHub Personal Access Token for private repos (optional)."
    )
    parser.add_argument(
        "--output-file",
        default=None,
        help="Filename for the export (default: <repo_name>_export.txt in exports/)."
    )
    parser.add_argument(
        "--skip-remove",
        action="store_true",
        help="Skip removing the cloned repository after exporting."
    )

    args = parser.parse_args()

    # Prompt for repo URL if not specified
    if not args.repo_url:
        args.repo_url = input("Enter the GitHub repository URL: ").strip()

    return args

def parse_github_url(url: str):
    """
    Parse a GitHub URL, possibly containing '/tree/<branch>/<subdir>'.
    Returns (actual_clone_url, extracted_branch).

    Example:
      Input:  https://github.com/owner/repo/tree/dev/docs/integrations
      Output: (https://github.com/owner/repo.git, 'dev')

      If no /tree/ is found, returns (original_url, None).
      If the original URL already ends with .git, it's kept as-is.

    We'll ignore subdir for simplicity (the script clones the entire repo).
    """
    pattern = r'^(https?://github\.com/[^/]+/[^/]+)(?:/tree/([^/]+)(?:/.*)?)?$'
    match = re.match(pattern, url)
    if match:
        base_repo = match.group(1)  # e.g. https://github.com/owner/repo
        extracted_branch = match.group(2)  # e.g. dev (optional)
        # Ensure .git at the end
        if not base_repo.endswith('.git'):
            base_repo += '.git'
        return base_repo, extracted_branch
    return url, None

def build_auth_url(base_url: str, token: str) -> str:
    """
    Build an authenticated URL for a private GitHub repo using a token.
    Example:
        base_url: https://github.com/owner/repo.git
        token:    ghp_123456...
        returns:  https://ghp_123456...@github.com/owner/repo.git

    For security, it is recommended not to show or log the full token.
    """
    if not base_url.startswith("https://"):
        logging.warning("Token-based auth is only set up for HTTPS. Proceeding without token.")
        return base_url
    return base_url.replace("https://", f"https://{token}@")

def prepare_exports_dir():
    """
    Create an 'exports/' directory in the current working directory,
    and add an entry to .gitignore so it won't be committed.
    """
    exports_dir = Path("exports")
    exports_dir.mkdir(exist_ok=True)

    gitignore_path = Path(".gitignore")
    if not gitignore_path.exists():
        # Create a simple .gitignore
        gitignore_path.write_text("exports/\n", encoding="utf-8")
        logging.info("Created .gitignore with 'exports/' entry.")
    else:
        # Append 'exports/' if not already in .gitignore
        with gitignore_path.open("r+", encoding="utf-8") as f:
            content = f.read()
            if "exports/" not in content:
                if not content.endswith("\n"):
                    f.write("\n")
                f.write("exports/\n")
                logging.info("Appended 'exports/' entry to existing .gitignore.")

    return exports_dir

def is_text_file(file_path: Path) -> bool:
    """
    Determine if the file is likely text or binary using MIME types.
    Returns True if recognized as text, False otherwise.
    """
    mime_type, _ = mimetypes.guess_type(str(file_path))
    # If mime_type is None or doesn't contain "text", we treat as non-text.
    return bool(mime_type) and "text" in mime_type

def export_files_to_single_file(repo: Repo, repo_name: str, repo_root: Path, output_file: Path) -> None:
    """
    Export text files (excluding tests) into a single text file, 
    preserving directory structure info and providing a final summary.

    Also logs total characters, lines, and tokens to the terminal.
    """
    total_chars = 0
    total_lines = 0
    total_tokens = 0

    with output_file.open("w", encoding="utf-8") as outfile:
        # Basic metadata
        try:
            branch_name = repo.active_branch.name
        except TypeError:
            branch_name = "HEAD detached or no branch"

        remote_url = (next(iter(repo.remotes[0].urls), "No remote URL") 
                      if repo.remotes else "No remote URL")
        outfile.write(f"Repository: {repo_name}\n")
        outfile.write(f"Branch: {branch_name}\n")
        outfile.write(f"Remote URL: {remote_url}\n")
        outfile.write("-" * 50 + "\n\n")

        # Walk the directory tree
        for root, dirs, files in os.walk(repo_root):
            # Exclude directories that contain 'test' in their name
            dirs[:] = [d for d in dirs if "test" not in d.lower()]

            for fname in files:
                # Skip hidden files or files containing 'test'
                if fname.startswith('.') or "test" in fname.lower():
                    continue

                file_path = Path(root) / fname
                # Skip .git or any path that has .git in it
                if ".git" in str(file_path):
                    continue

                # Skip non-text files
                if not is_text_file(file_path):
                    continue

                rel_path = file_path.relative_to(repo_root)
                outfile.write(f"===== START OF {rel_path} =====\n")

                # Last commit info
                try:
                    last_commit = next(repo.iter_commits(paths=str(rel_path), max_count=1))
                    commit_msg = last_commit.message.strip()
                    author = last_commit.author.name
                    commit_date = last_commit.committed_datetime
                    outfile.write(f"Last Commit: {commit_msg} by {author} on {commit_date}\n")
                except StopIteration:
                    outfile.write("Last Commit: No commits found\n")

                # File content
                try:
                    with file_path.open("r", encoding="utf-8", errors="ignore") as infile:
                        content = infile.read()
                        outfile.write(content)
                        total_chars += len(content)
                        total_lines += content.count('\n') + 1
                        total_tokens += len(content.split())
                except Exception as e:
                    outfile.write(f"Error reading file: {e}\n")

                outfile.write(f"\n===== END OF {rel_path} =====\n\n")

        # Append the summary at the end of the file
        outfile.write("\n--- Summary ---\n")
        outfile.write(f"Total characters: {total_chars}\n")
        outfile.write(f"Total lines: {total_lines}\n")
        outfile.write(f"Total tokens: {total_tokens}\n")

    # Also print summary to the terminal
    logging.info("Export completed.")
    logging.info(f"Total characters: {total_chars}")
    logging.info(f"Total lines: {total_lines}")
    logging.info(f"Total tokens: {total_tokens}")

def clone_and_export(args: argparse.Namespace) -> None:
    """
    Clone the GitHub repository (optionally with a token),
    switch to the appropriate branch, export text files, and 
    optionally remove the cloned repo.
    """
    # Prepare the exports directory and ensure .gitignore excludes it
    exports_dir = prepare_exports_dir()

    # Extract branch if URL includes '/tree/...'
    parsed_url, extracted_branch = parse_github_url(args.repo_url)

    # If user didn't explicitly set --branch, but we parsed one, use it
    final_branch = args.branch or extracted_branch

    # Masked token logging
    if args.token:
        masked_token = args.token[:3] + "..." + args.token[-3:] if len(args.token) > 6 else "REDACTED"
        logging.info(f"Using token: {masked_token}")
        parsed_url = build_auth_url(parsed_url, args.token)

    # Figure out the repo name from the final clone URL
    repo_name = parsed_url.rstrip("/").split("/")[-1].replace(".git", "")

    # Determine output filename and place it in the `exports/` directory
    if args.output_file:
        output_path = exports_dir / args.output_file
    else:
        output_path = exports_dir / f"{repo_name}_export.txt"

    with tempfile.TemporaryDirectory() as tmpdir:
        clone_path = Path(tmpdir) / repo_name
        logging.info(f"Cloning into temporary directory: {clone_path}")

        # Run git clone quietly
        try:
            subprocess.run(
                ["git", "clone", parsed_url, str(clone_path)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except subprocess.CalledProcessError as e:
            logging.error(f"Git clone failed: {e}")
            return

        # Initialize repo object
        try:
            repo = Repo(clone_path)
        except exc.GitError as e:
            logging.error(f"Failed to initialize repository: {e}")
            return

        # If we have a branch to check out, do it
        if final_branch:
            logging.info(f"Checking out branch/commit: {final_branch}")
            try:
                repo.git.checkout(final_branch)
            except exc.GitCommandError as e:
                logging.error(f"Failed to checkout {final_branch}: {e}")
                return

        # Export files
        export_files_to_single_file(repo, repo_name, clone_path, output_path)
        logging.info(f"Repository exported to {output_path}")

        if args.skip_remove:
            logging.info("Skipping removal of cloned repository as requested.")
        else:
            logging.info("Temporary directory (and cloned repo) will be removed automatically.")

def main():
    args = parse_args()
    clone_and_export(args)

if __name__ == "__main__":
    main()
