#!/usr/bin/env python3
"""
file2ai Exporter

Clones a GitHub repository or exports text files from a local directory to a single text file.
"""

from __future__ import annotations

import argparse
import fnmatch
import logging
import mimetypes
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Set, NoReturn, TextIO, Dict, List, TypedDict, Union
import json


class CommitInfo(TypedDict, total=False):
    message: str
    author: str
    date: str


class FileEntry(TypedDict):
    path: str
    content: str
    last_commit: Optional[CommitInfo]


# Version and constants
VERSION: str = "1.0.1"
MIN_PYTHON_VERSION: Tuple[int, int] = (3, 7)
DEFAULT_ENCODING: str = "utf-8"
LAUNCHER_DIR_NAME: str = "launchers"
LOGS_DIR: str = "logs"
EXPORTS_DIR: str = "exports"

# File extension sets
TEXT_EXTENSIONS: Set[str] = {
    ".txt",
    ".py",
    ".md",
    ".json",
    ".yml",
    ".yaml",
    ".ini",
    ".cfg",
    ".sh",
    ".bash",
    ".js",
    ".css",
    ".html",
    ".xml",
    ".rst",
    ".bat",
    ".java",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".rb",
    ".php",
    ".go",
    ".rs",
}

BINARY_EXTENSIONS: Set[str] = {
    ".bin",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".pdf",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".zip",
    ".tar",
    ".gz",
}

# Initialize logger
logger = logging.getLogger(__name__)


def install_gitpython_quietly() -> None:
    """Install GitPython package quietly using pip."""
    logger.info("Installing dependencies... (this may take a moment)")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "gitpython", "--quiet"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install GitPython: {e}")
        raise SystemExit(1)


def ensure_gitpython() -> None:
    """Ensure GitPython is available, installing if necessary."""
    try:
        import git  # type: ignore # noqa: F401
    except ImportError:
        install_gitpython_quietly()


# Ensure GitPython is available before importing
ensure_gitpython()
from git import Repo, exc  # noqa: E402


def setup_logging() -> None:
    """Configure logging with file and console output."""
    logs_dir = Path(LOGS_DIR)
    logs_dir.mkdir(exist_ok=True)

    # Configure logging handlers
    log_file = logs_dir / f"file2ai_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding=DEFAULT_ENCODING),
            logging.StreamHandler(sys.stdout),
        ],
    )


def validate_github_url(url: str) -> bool:
    """Validate that the URL is a GitHub repository URL."""
    if not url:
        return False
    return bool(re.match(r"^https?://github\.com/[^/]+/[^/]+", url))


def parse_args() -> argparse.Namespace:
    """
    Parse and validate command-line arguments.

    Logic:
        - If --local-dir is provided, use that directly
        - If --repo-url is provided, use that directly
        - If neither is provided, prompt user for input
    """
    parser = argparse.ArgumentParser(
        description="Clone a GitHub repo or export text files from a local directory to a single file.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Repository source group (mutually exclusive)
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument(
        "--repo-url",
        help="GitHub repository URL (e.g., https://github.com/owner/repo)",
    )
    source_group.add_argument(
        "--repo-url-sub",
        help="GitHub repository URL with subdirectory to process",
    )
    source_group.add_argument(
        "--local-dir",
        help="Local directory path to export",
    )

    # Optional arguments that must come before the URL
    parser.add_argument("--branch", help="Branch or commit to checkout (optional)")
    parser.add_argument("--subdir", help="Optional subdirectory to export (defaults to repo root)")
    parser.add_argument("--token", help="GitHub Personal Access Token for private repos")

    parser.add_argument(
        "--output-file", help="Custom output filename (default: <repo_name>_export.txt)"
    )

    parser.add_argument(
        "--skip-remove", action="store_true", help="Skip removal of cloned repository after export"
    )

    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Choose the output format (text or json). Default is text.",
    )

    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")

    args = parser.parse_args()

    # Initialize attributes
    if not hasattr(args, 'repo_url'):
        args.repo_url = None
    if not hasattr(args, 'local_dir'):
        args.local_dir = None
    if not hasattr(args, 'repo_url_sub'):
        args.repo_url_sub = False

    # Process command-line arguments if provided
    if args.local_dir:
        args.repo_url_sub = False
        return args
    if args.repo_url:
        args.repo_url_sub = False
        return args
    if args.repo_url_sub:
        args.repo_url = args.repo_url_sub
        args.repo_url_sub = True
        return args

    # Only prompt if no source arguments were provided
    tmp_url = input(
        "Enter the GitHub repository URL (or press Enter to export local directory): "
    ).strip()
    if tmp_url:
        args.repo_url = tmp_url
    else:
        tmp_dir = input(
            "Enter a local directory path for export (or press Enter for current directory): "
        ).strip()
        if tmp_dir:
            args.local_dir = tmp_dir
        else:
            args.local_dir = os.getcwd()
            logger.info(
                f"No directory specified, defaulting to current directory: {args.local_dir}"
            )

    return args


def parse_github_url(url: str, use_subdirectory: bool = False) -> Tuple[str, Optional[str], Optional[str]]:
    """
    Extract information from a GitHub repository URL, ignoring subdirectories unless use_subdirectory is True.
    Also extracts base repository URL from deep URLs like /pulls, /issues, etc.

    Args:
        url: The GitHub repository URL to parse.
        use_subdirectory: If True, extract subdirectory information from deep URLs.

    Returns:
        Tuple of (base_repo_url, branch, subdirectory).
        - base_repo_url: The base GitHub repository URL ending with .git
        - branch: Branch name if specified in URL, None otherwise
        - subdirectory: Subdirectory path if specified and use_subdirectory=True, None otherwise

    Raises:
        SystemExit: If the URL is not a valid GitHub repository URL.
    """
    # Step 1: Extract base repository URL first
    base_match = re.match(r"^(https?://github\.com/[^/]+/[^/]+)", url)
    if not base_match:
        logger.error(f"Invalid GitHub URL: {url}")
        sys.exit(1)
    
    base_repo = base_match.group(1)
    remaining_path = url[len(base_repo):]

    # Step 2: Check for URL suffixes that could be subdirectories
    special_suffixes = ["/pulls", "/issues", "/actions", "/wiki"]
    subdir = None
    for suffix in special_suffixes:
        if remaining_path.startswith(suffix):
            if use_subdirectory:
                # These are GitHub virtual paths, warn user they don't exist in repo
                logger.warning(
                    f"{suffix} is a GitHub virtual path and doesn't exist in the repository. "
                    "Exporting from repository root instead."
                )
            else:
                # Otherwise just remove it and continue with base URL
                logger.warning(f"Removing suffix {suffix} from URL: {url}")
            remaining_path = remaining_path[len(suffix):]
            break

    # Step 3: Check for tree/<branch>/<path> pattern
    tree_match = re.search(r"/tree/([^/]+)(?:/(.+))?$", url)
    branch = tree_match.group(1) if tree_match else None
    
    # If we already have a subdir from special suffixes, don't override it
    if not subdir:
        subdir = tree_match.group(2) if tree_match and use_subdirectory else None

    # Step 4: Append .git if missing
    if not base_repo.endswith(".git"):
        base_repo += ".git"

    return base_repo, branch, subdir


def build_auth_url(base_url: str, token: str) -> str:
    """
    Build an authenticated GitHub URL using a token.

    Args:
        base_url: The base GitHub repository URL.
        token: The GitHub Personal Access Token.

    Returns:
        The authenticated URL.
    """
    if not base_url.startswith("https://"):
        logger.warning("Token-based auth requires HTTPS. Proceeding without token.")
        return base_url
    return base_url.replace("https://", f"https://{token}@")


def is_text_file(file_path: Path) -> bool:
    """
    Determine if a file is text-based by:
      1) Checking if its suffix is in a known binary or text set
      2) Checking MIME type (if available)
      3) Scanning first 1KB for null bytes as a fallback
    """
    suffix = file_path.suffix.lower()

    # 1) Immediate check against known binary or text extensions
    if suffix in BINARY_EXTENSIONS:
        return False
    if suffix in TEXT_EXTENSIONS:
        return True

    # 2) MIME type guess
    mime_type, _ = mimetypes.guess_type(str(file_path))
    if mime_type:
        # If MIME starts with "text/", or is specifically "application/json", "application/xml", etc.
        # treat it as text
        if mime_type.startswith("text/"):
            return True
        if mime_type in ("application/json", "application/xml"):
            return True
        # If we get something like application/octet-stream, it's probably binary
        return False

    # 3) Read first 1KB; if we see a null byte, consider it binary
    try:
        with file_path.open("rb") as f:
            chunk = f.read(1024)
            if b"\x00" in chunk:
                return False
    except IOError:
        return False

    # If we pass all the above checks without finding a reason to skip,
    # assume it is text-ish
    return True


def _sequential_filename(output_path: Path) -> Path:
    """
    Append (1), (2), etc. to the output file if it already exists to avoid overwriting.
    Ensures sequential numbering by checking all existing files first.
    """
    if not output_path.exists():
        return output_path

    base = output_path.stem
    suffix = output_path.suffix
    parent = output_path.parent

    # Find all existing sequential files
    existing_files = list(parent.glob(f"{base}(*){suffix}"))
    counter = 1

    if existing_files:
        # Extract numbers from existing files and find the highest
        numbers = []
        for f in existing_files:
            try:
                num = int(f.stem[len(base)+1:-1])  # Extract number between parentheses
                numbers.append(num)
            except (ValueError, IndexError):
                continue
        if numbers:
            counter = max(numbers) + 1

    # Create new filename with next available number
    output_path = parent / f"{base}({counter}){suffix}"
    logger.debug(f"Using sequential filename: {output_path}")
    return output_path


def prepare_exports_dir() -> Path:
    """
    Create and configure the exports directory.

    Returns:
        Path to the exports directory.
    """
    exports_dir = Path("exports")
    exports_dir.mkdir(exist_ok=True)
    return exports_dir

def load_gitignore_patterns(repo_root: Path) -> Tuple[Set[str], Set[str]]:
    """
    Load .gitignore patterns from the repository root.
    Implements blanket ignore by default with "*" pattern.
    Supports pattern overrides with "!" prefix.
    
    Args:
        repo_root: Path to the repository root directory.
    
    Returns:
        Tuple of (ignore_patterns, override_patterns).
        - ignore_patterns: Set of patterns to ignore
        - override_patterns: Set of patterns to explicitly include
    """
    # Default patterns to ignore common unwanted files
    ignore_patterns = {
        "__pycache__/*", "*.pyc", "*.pyo", "*.pyd",
        "*.so", "*.dll", "*.dylib",
        "*.exe", "*.bin",
        "*.jpg", "*.jpeg", "*.png", "*.gif",
        "*.pdf", "*.zip", "*.tar.gz",
        ".git/*", ".svn/*", ".hg/*",
        "node_modules/*", "venv/*", ".env/*"
    }
    override_patterns = set()
    gitignore_path = repo_root / ".gitignore"
    
    if gitignore_path.is_file():
        try:
            with gitignore_path.open(encoding=DEFAULT_ENCODING) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                        
                    if line.startswith('!'):
                        pattern = line[1:]  # Remove the ! prefix
                        override_patterns.add(pattern)
                        logger.debug(f"Added override pattern: {pattern}")
                    else:
                        ignore_patterns.add(line)
                        
            logger.debug(f"Loaded {len(ignore_patterns)} ignore patterns and {len(override_patterns)} override patterns")
        except Exception as e:
            logger.warning(f"Error reading .gitignore: {e}")
    else:
        logger.debug("No .gitignore found, using default blanket ignore")
    
    return ignore_patterns, override_patterns

def should_ignore(path: Path, patterns: Tuple[Set[str], Set[str]], repo_root: Path) -> bool:
    """
    Check if a path should be ignored based on .gitignore patterns.
    Supports blanket ignore with pattern overrides.
    
    Args:
        path: Path to check.
        patterns: Tuple of (ignore_patterns, override_patterns) from load_gitignore_patterns.
        repo_root: Repository root path for relative path calculation.
    
    Returns:
        True if the path should be ignored, False otherwise.
    """
    # Always check if it's a binary file first
    if not is_text_file(path):
        logger.info(f"Skipped binary file: {path}")
        return True

    ignore_patterns, override_patterns = patterns
    if not ignore_patterns and not override_patterns:
        return False
        
    try:
        rel_path = str(path.relative_to(repo_root))
        
        # First check if path matches any override patterns
        for pattern in override_patterns:
            if fnmatch.fnmatch(rel_path, pattern):
                logger.debug(f"Including {rel_path} (matches override pattern {pattern})")
                return False
                
        # Then check if path matches any ignore patterns
        for pattern in ignore_patterns:
            if fnmatch.fnmatch(rel_path, pattern):
                logger.debug(f"Ignoring {rel_path} (matches ignore pattern {pattern})")
                return True
                
    except Exception as e:
        logger.warning(f"Error checking ignore pattern for {path}: {e}")
        return True  # Default to ignore on error
        
    return False  # Default to include if no patterns match


def export_files_to_single_file(
    repo: Optional[Repo],
    repo_name: str,
    repo_root: Path,
    output_file: Path,
    skip_commit_info: bool = False,
) -> None:
    """
    Export repository (or local dir) text files to a single file.

    Args:
        repo: The Git repository object (if any; can be None for a non-git local dir).
        repo_name: Name of the repository or "local-export".
        repo_root: Root path of the repository or local directory.
        output_file: Path to the output file.
        skip_commit_info: If True, do not attempt to read Git commit info.
    """
    logger.info("Starting file export process")
    stats: Dict[str, int] = {
        "processed_files": 0,
        "skipped_files": 0,
        "total_chars": 0,
        "total_lines": 0,
        "total_tokens": 0,
    }

    # Ensure output directory exists and resolve path
    output_file = Path(output_file).resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Writing to output file: {output_file}")

    with output_file.open("w", encoding=DEFAULT_ENCODING) as outfile:
        # Write header
        outfile.write("Generated by file2ai\n")
        outfile.write("=" * 80 + "\n\n")
        outfile.write(f"Repository: {repo_name}\n\n")

        # Directory structure
        outfile.write("Directory Structure:\n")
        outfile.write("------------------\n")
        _write_directory_structure(repo_root, outfile)
        outfile.write("\n" + "=" * 80 + "\n\n")

        # Process files
        _process_repository_files(repo_root, outfile, stats, repo if not skip_commit_info else None)

        # Write summary
        _write_summary(outfile, stats)

    _log_export_stats(stats)


def export_files_to_json(
    repo: Optional[Repo],
    repo_name: str,
    repo_root: Path,
    output_file: Path,
    skip_commit_info: bool = False,
) -> None:
    """
    Export repository (or local dir) text files to a JSON file.

    Args:
        repo: The Git repository object (if any; can be None for a non-git local dir).
        repo_name: Name of the repository or "local-export".
        repo_root: Root path of the repository or local directory.
        output_file: Path to the output file.
        skip_commit_info: If True, do not attempt to read Git commit info.
    """
    logger.info("Starting JSON export process")
    stats: Dict[str, int] = {
        "processed_files": 0,
        "skipped_files": 0,
        "total_chars": 0,
        "total_lines": 0,
        "total_tokens": 0,
    }

    data: List[FileEntry] = []
    ignore_patterns = load_gitignore_patterns(repo_root)
    
    files_to_process = [
        f
        for f in repo_root.rglob("*")
        if f.is_file()
        and not f.name.startswith(".")
        and ".git" not in str(f)
        and not should_ignore(f, ignore_patterns, repo_root)
    ]
    total_files = len(files_to_process)

    for i, file_path in enumerate(files_to_process, 1):
        if i % 10 == 0:  # Update every 10 files
            logger.info(f"Processing files: {i}/{total_files}")

        if is_text_file(file_path):
            try:
                content = file_path.read_text(encoding=DEFAULT_ENCODING)
                rel_path = file_path.relative_to(repo_root)

                file_entry: FileEntry = {
                    "path": str(rel_path),
                    "content": content,
                    "last_commit": None,
                }

                if repo and not skip_commit_info:
                    try:
                        last_commit = next(repo.iter_commits(paths=str(rel_path), max_count=1))
                        commit_info: CommitInfo = {
                            "message": str(last_commit.message.strip()),
                            "author": str(last_commit.author.name),
                            "date": str(last_commit.committed_datetime.isoformat()),
                        }
                        file_entry["last_commit"] = commit_info
                    except (StopIteration, Exception) as e:
                        if not isinstance(e, StopIteration):
                            logger.warning(f"Could not get commit info for {file_path}: {e}")
                        # last_commit is already None by default

                data.append(file_entry)

                # Update stats
                stats["processed_files"] += 1
                stats["total_chars"] += len(content)
                stats["total_lines"] += content.count("\n") + 1
                stats["total_tokens"] += len(content.split())

                logger.debug(f"Processed file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to process {file_path}: {e}")
                stats["skipped_files"] += 1
        else:
            logger.debug(f"Skipped binary file: {file_path}")
            stats["skipped_files"] += 1

    # Write JSON output
    with output_file.open("w", encoding=DEFAULT_ENCODING) as f:
        json.dump({"repository": repo_name, "files": data}, f, indent=2)

    _log_export_stats(stats)


def _write_directory_structure(repo_root: Path, outfile: TextIO) -> None:
    """Write the repository/local directory structure to the output file."""
    ignore_patterns = load_gitignore_patterns(repo_root)
    
    for root, dirs, files in os.walk(repo_root):
        rel_path = Path(root).relative_to(repo_root)
        
        # Skip .git directory
        if ".git" in str(rel_path):
            continue
            
        # Check if directory should be ignored
        if should_ignore(Path(root), ignore_patterns, repo_root):
            logger.debug(f"Skipping ignored directory: {rel_path}")
            dirs.clear()  # Skip processing subdirectories
            continue
            
        level = len(rel_path.parts)
        
        # Print directory name (except root)
        if str(rel_path) != ".":
            outfile.write(f"{'  ' * (level-1)}└── {rel_path.name}/\n")
            
        # Process files
        for file in sorted(files):
            file_path = Path(root) / file
            if not file.startswith(".") and "test" not in file.lower():
                if not should_ignore(file_path, ignore_patterns, repo_root):
                    outfile.write(f"{'  ' * level}└── {file}\n")
                else:
                    logger.debug(f"Skipping ignored file: {file_path}")


def _process_repository_files(
    repo_root: Path, outfile: TextIO, stats: Dict[str, int], repo: Optional[Repo]
) -> None:
    """Process all repository files and update statistics."""
    ignore_patterns = load_gitignore_patterns(repo_root)
    
    files_to_process = [
        f
        for f in repo_root.rglob("*")
        if f.is_file() 
        and not f.name.startswith(".")
        and ".git" not in str(f)
        and not should_ignore(f, ignore_patterns, repo_root)
    ]
    total_files = len(files_to_process)

    for i, file_path in enumerate(files_to_process, 1):
        if i % 10 == 0:  # Update every 10 files
            logger.info(f"Processing files: {i}/{total_files}")
        if is_text_file(file_path):
            try:
                content = file_path.read_text(encoding=DEFAULT_ENCODING)

                # Write file header
                outfile.write(f"File: {file_path}\n")
                outfile.write("-" * 80 + "\n")

                if repo:
                    # Attempt to get last commit info if the file is tracked in Git
                    rel_path = file_path.relative_to(repo_root)
                    try:
                        last_commit = next(repo.iter_commits(paths=str(rel_path), max_count=1))
                        commit_msg = last_commit.message.strip()
                        author = last_commit.author.name
                        commit_date = last_commit.committed_datetime.isoformat()[:10]  # Get YYYY-MM-DD part
                        outfile.write(f"Last Commit: {commit_msg} by {author} on {commit_date}\n\n")
                    except StopIteration:
                        outfile.write("Last Commit: No commits found\n\n")
                    except Exception as e:
                        logger.warning(f"Could not get commit info for {file_path}: {e}")
                        outfile.write("Last Commit: Unknown\n\n")

                # Write file content
                outfile.write(content)
                outfile.write("\n" + "=" * 80 + "\n\n")

                # Update stats
                stats["processed_files"] += 1
                stats["total_chars"] += len(content)
                stats["total_lines"] += content.count("\n") + 1
                stats["total_tokens"] += len(content.split())

                logger.debug(f"Processed file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to process {file_path}: {e}")
                stats["skipped_files"] += 1
        else:
            logger.debug(f"Skipped binary file: {file_path}")
            stats["skipped_files"] += 1


def _write_summary(outfile: TextIO, stats: Dict[str, int]) -> None:
    """Write export statistics summary to the output file."""
    outfile.write("\nFile Statistics:\n")
    outfile.write("--------------\n")
    outfile.write(f"Total files processed: {stats['processed_files']}\n")
    outfile.write(f"Total files skipped: {stats['skipped_files']}\n")
    outfile.write(f"Total characters: {stats['total_chars']:,}\n")
    outfile.write(f"Total lines: {stats['total_lines']:,}\n")
    outfile.write(f"Total tokens: {stats['total_tokens']:,}\n")


def _log_export_stats(stats: dict) -> None:
    """Log export statistics to the console."""
    logger.info(
        f"Export complete. Processed {stats['processed_files']} files, "
        f"skipped {stats['skipped_files']} files"
    )
    logger.info(f"Total characters: {stats['total_chars']:,}")
    logger.info(f"Total lines: {stats['total_lines']:,}")
    logger.info(f"Total tokens: {stats['total_tokens']:,}")


def clone_and_export(args: argparse.Namespace) -> None:
    """
    Clone repository and export its contents.

    Args:
        args: Command line arguments namespace.
    """
    logger.info(f"Starting export of repository: {args.repo_url}")
    exports_dir = Path(EXPORTS_DIR)
    exports_dir.mkdir(parents=True, exist_ok=True)

    # Parse URL and extract components based on --repo-url-sub flag
    clone_url, url_branch, url_subdir = parse_github_url(
        args.repo_url,
        use_subdirectory=args.repo_url_sub
    )

    # Use token if provided
    if args.token:
        masked_token = (
            f"{args.token[:3]}...{args.token[-3:]}" if len(args.token) > 6 else "REDACTED"
        )
        logger.info(f"Using token: {masked_token}")
        clone_url = build_auth_url(clone_url, args.token)

    repo_name = clone_url.rstrip("/").split("/")[-1].replace(".git", "")
    extension = ".json" if args.format == "json" else ".txt"
    output_path = exports_dir / (args.output_file or f"{repo_name}_export{extension}")
    output_path = _sequential_filename(output_path.resolve())
    logger.debug(f"Using output path: {output_path}")

    with tempfile.TemporaryDirectory() as temp_dir:
        clone_path = Path(temp_dir) / repo_name
        logger.info(f"Cloning repository to: {clone_path}")

        try:
            subprocess.run(
                ["git", "clone", clone_url, str(clone_path)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
            logger.info("Repository cloned successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Git clone failed: {e}")
            sys.exit(1)

        try:
            repo = Repo(clone_path)
        except exc.GitError as e:
            logger.error(f"Failed to initialize repository: {e}")
            sys.exit(1)

        # Determine branch: explicit --branch flag takes precedence over URL
        branch = args.branch or url_branch
        if branch:
            try:
                repo.git.checkout(branch)
                logger.info(f"Checked out branch: {branch}")
            except exc.GitCommandError as e:
                logger.error(f"Failed to checkout {branch}: {e}")
                sys.exit(1)
        else:
            logger.info("Using default branch")

        # Determine subdirectory: explicit --subdir flag takes precedence over URL
        subdir = args.subdir or url_subdir
        if subdir:
            export_target = clone_path / subdir
            if not export_target.is_dir():
                logger.error(f"Subdirectory {subdir} does not exist in the repository")
                sys.exit(1)
            logger.info(f"Exporting from subdirectory: {subdir}")
        else:
            export_target = clone_path
            logger.info("Exporting from repository root")

        if args.format == "json":
            export_files_to_json(repo, repo_name, export_target, output_path)
        else:
            export_files_to_single_file(repo, repo_name, export_target, output_path)
        logger.info(f"Repository exported to {output_path}")

        if not args.skip_remove:
            try:
                repo.close()
                logger.info("Cleaned up temporary repository")
            except Exception as e:
                logger.warning(f"Failed to clean up repository: {e}")


def local_export(args: argparse.Namespace) -> None:
    """
    Recursively export text files from a local directory.

    Args:
        args: Command line arguments namespace.
    """
    logger.info("Starting export of local directory")
    local_dir = Path(args.local_dir)
    repo_name = local_dir.name or "local-export"
    extension = ".json" if args.format == "json" else ".txt"
    output_file = args.output_file or f"{repo_name}_export{extension}"
    output_path = Path(EXPORTS_DIR) / output_file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path = _sequential_filename(output_path.resolve())
    logger.debug(f"Using output path: {output_path}")
    logger.debug(f"Exports directory: {EXPORTS_DIR}")

    # Check if local_dir is a git repository
    git_path = local_dir / ".git"
    if git_path.is_dir():
        # Attempt to open a Repo object so we can capture commit info
        try:
            repo = Repo(local_dir)
            logger.info(f"Found local git repository: {local_dir}")
            if args.format == "json":
                export_files_to_json(
                    repo, repo_name, local_dir, output_path, skip_commit_info=False
                )
            else:
                export_files_to_single_file(
                    repo, repo_name, local_dir, output_path, skip_commit_info=False
                )
        except exc.GitError:
            logger.warning(
                "Local directory has .git but is not a valid repo. Skipping commit info."
            )
            if args.format == "json":
                export_files_to_json(None, repo_name, local_dir, output_path, skip_commit_info=True)
            else:
                export_files_to_single_file(
                    None, repo_name, local_dir, output_path, skip_commit_info=True
                )
    else:
        # Not a git repository at all
        logger.info(f"Local directory is not a git repository: {local_dir}")
        if args.format == "json":
            export_files_to_json(None, repo_name, local_dir, output_path, skip_commit_info=True)
        else:
            export_files_to_single_file(
                None, repo_name, local_dir, output_path, skip_commit_info=True
            )

    # Ensure we use absolute paths
    output_path = Path(output_path).resolve()
    logger.info(f"Local directory exported to {output_path}")
    logger.debug(f"Output path (absolute): {output_path}")


def load_config() -> dict:
    """Load configuration from file2ai.conf if it exists."""
    config_path = Path("file2ai.conf")
    if config_path.exists():
        return json.loads(config_path.read_text())
    return {}


def main() -> NoReturn:
    """Main entry point."""
    setup_logging()
    logger.info(f"Starting file2ai version {VERSION}")
    args = parse_args()

    if args.local_dir:
        # Export from local directory
        local_export(args)
    else:
        # Clone from remote repo and export
        clone_and_export(args)

    logger.info("file2ai completed successfully")
    sys.exit(0)


if __name__ == "__main__":
    main()
