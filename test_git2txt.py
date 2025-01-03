import json
import pytest
import shutil
from pathlib import Path
import sys
from unittest.mock import patch, MagicMock
from git2txt import (
    parse_args,
    is_text_file,
    validate_github_url,
    export_files_to_json,
    export_files_to_single_file,
    parse_github_url,
    build_auth_url,
    prepare_exports_dir,
    clone_and_export,
    local_export,
)


def test_parse_args_repo(monkeypatch):
    """Test argument parsing with repo URL."""
    monkeypatch.setattr(
        sys, "argv", ["git2txt.py", "--repo-url", "https://github.com/owner/repo.git"]
    )
    args = parse_args()
    assert args.repo_url == "https://github.com/owner/repo.git"
    assert args.local_dir is None


def test_parse_args_local(monkeypatch):
    """Test argument parsing with local directory."""
    monkeypatch.setattr(sys, "argv", ["git2txt.py", "--local-dir", "/path/to/dir"])
    args = parse_args()
    assert args.local_dir == "/path/to/dir"
    assert args.repo_url is None


def test_parse_args_interactive(monkeypatch):
    """Test argument parsing with interactive input."""
    inputs = ["https://github.com/owner/repo.git", ""]
    input_iter = iter(inputs)
    monkeypatch.setattr("builtins.input", lambda _: next(input_iter))
    monkeypatch.setattr("sys.argv", ["git2txt.py"])
    args = parse_args()
    assert args.repo_url == "https://github.com/owner/repo.git"
    assert args.local_dir is None


def test_is_text_file(tmp_path):
    """Test text file detection."""
    # Test Python file
    py_file = tmp_path / "example.py"
    py_file.write_text("print('Hello')")
    assert is_text_file(py_file) is True

    # Test binary file
    bin_file = tmp_path / "example.bin"
    bin_file.write_bytes(b"\x00\x01\x02\x03")
    assert is_text_file(bin_file) is False


def test_validate_github_url():
    """Test GitHub URL validation."""
    assert validate_github_url("https://github.com/owner/repo") is True
    assert validate_github_url("https://github.com/owner/repo.git") is True
    assert validate_github_url("not_a_url") is False
    assert validate_github_url("") is False


def test_json_export_error_handling(tmp_path, caplog):
    """Test JSON export error handling with invalid files."""
    import logging
    from git2txt import setup_logging

    setup_logging()
    caplog.set_level(logging.DEBUG)

    # Create a sample directory with a binary file
    sample_dir = tmp_path / "error_project"
    sample_dir.mkdir()
    binary_file = sample_dir / "binary.dat"
    binary_file.write_bytes(b"\x00\x01\x02\x03")

    # Create output file
    output_file = tmp_path / "error_export.json"

    # Export to JSON
    export_files_to_json(None, "error-test", sample_dir, output_file, skip_commit_info=True)

    # Verify JSON structure
    with output_file.open() as f:
        data = json.load(f)
        assert data["repository"] == "error-test"
        assert len(data["files"]) == 0  # No files should be exported

    # Check if skipped file was logged with exact message
    assert f"Skipped binary file: {binary_file}" in caplog.text


def test_json_export_basic(tmp_path, caplog):
    """Test basic JSON export functionality without git repo."""
    # Verify logging is initialized
    from git2txt import setup_logging

    setup_logging()
    # Create a sample file
    sample_dir = tmp_path / "sample_project"
    sample_dir.mkdir()
    sample_file = sample_dir / "hello.txt"
    sample_file.write_text("Hello, World!")

    # Create output file
    output_file = tmp_path / "output.json"

    # Export to JSON
    export_files_to_json(None, "test-export", sample_dir, output_file, skip_commit_info=True)

    # Verify JSON structure
    with output_file.open() as f:
        data = json.load(f)
        assert "repository" in data
        assert data["repository"] == "test-export"
        assert "files" in data
        assert len(data["files"]) == 1

        file_entry = data["files"][0]
        assert file_entry["path"] == "hello.txt"
        assert file_entry["content"] == "Hello, World!"
        assert file_entry["last_commit"] is None


@pytest.mark.parametrize("format_arg", ["text", "json"])
def test_format_argument(format_arg, monkeypatch):
    """Test that --format argument is correctly parsed."""
    monkeypatch.setattr(sys, "argv", ["git2txt.py", "--local-dir", ".", "--format", format_arg])
    args = parse_args()
    assert args.format == format_arg


def test_json_export_with_git(tmp_path, caplog):
    """Test JSON export with mocked git repository."""
    # Verify logging is initialized
    from git2txt import setup_logging

    setup_logging()
    # Create a sample file
    sample_dir = tmp_path / "git_project"
    sample_dir.mkdir()
    sample_file = sample_dir / "code.py"
    sample_file.write_text("print('Hello Git')")

    # Mock Git objects
    mock_commit = MagicMock()
    mock_commit.message = "Initial commit"
    mock_commit.author.name = "Test Author"
    mock_commit.committed_datetime.isoformat.return_value = "2023-01-01T00:00:00"

    mock_repo = MagicMock()
    mock_repo.iter_commits.return_value = iter([mock_commit])

    # Create output file
    output_file = tmp_path / "repo_export.json"

    # Export to JSON
    export_files_to_json(mock_repo, "git-project", sample_dir, output_file)

    # Verify JSON structure
    with output_file.open() as f:
        data = json.load(f)
        assert data["repository"] == "git-project"
        assert len(data["files"]) == 1

        file_entry = data["files"][0]
        assert file_entry["path"] == "code.py"
        assert file_entry["content"] == "print('Hello Git')"
        assert file_entry["last_commit"] is not None
        assert file_entry["last_commit"]["message"] == "Initial commit"
        assert file_entry["last_commit"]["author"] == "Test Author"
        assert file_entry["last_commit"]["date"] == "2023-01-01T00:00:00"


def test_parse_github_url():
    """Test GitHub URL parsing and validation."""
    # Test basic URL
    url = parse_github_url("https://github.com/owner/repo.git")
    assert url == "https://github.com/owner/repo.git"

    # Test URL without .git (should add it)
    url = parse_github_url("https://github.com/owner/repo")
    assert url == "https://github.com/owner/repo.git"

    # Test invalid URLs
    with pytest.raises(SystemExit):
        parse_github_url("https://github.com/owner/repo/pulls")
    
    with pytest.raises(SystemExit):
        parse_github_url("https://github.com/owner/repo/issues")
    
    with pytest.raises(SystemExit):
        parse_github_url("https://github.com/owner/repo/tree/main")
    
    with pytest.raises(SystemExit):
        parse_github_url("not_a_url")


def test_build_auth_url():
    """Test building authenticated GitHub URL."""
    base_url = "https://github.com/owner/repo.git"
    token = "ghp_123456789"
    auth_url = build_auth_url(base_url, token)
    assert auth_url == "https://ghp_123456789@github.com/owner/repo.git"


def test_prepare_exports_dir(tmp_path):
    """Test exports directory preparation."""
    with patch("git2txt.EXPORTS_DIR", str(tmp_path / "exports")):
        exports_dir = prepare_exports_dir()
        assert exports_dir.exists()
        assert exports_dir.is_dir()


def test_clone_and_export_basic(tmp_path, caplog):
    """Test basic repository cloning and export with branch and subdirectory handling."""
    import logging
    from git2txt import setup_logging
    import subprocess

    setup_logging()
    logger = logging.getLogger("git2txt")
    caplog.set_level(logging.INFO)

    # Create a temporary git repository
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    
    # Create main test file
    (repo_dir / "test.py").write_text("print('test')")
    
    # Create subdirectory with content
    subdir = repo_dir / "subdir"
    subdir.mkdir()
    (subdir / "subfile.py").write_text("print('subdir test')")

    # Initialize git repo
    subprocess.run(["git", "init", "--initial-branch=main"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "test"], cwd=repo_dir, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True, capture_output=True
    )
    
    # Create and switch to test branch
    subprocess.run(["git", "checkout", "-b", "test-branch"], cwd=repo_dir, check=True, capture_output=True)
    (repo_dir / "branch-file.py").write_text("print('branch test')")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Branch commit"], cwd=repo_dir, check=True, capture_output=True
    )
    
    # Switch back to main
    subprocess.run(["git", "checkout", "main"], cwd=repo_dir, check=True, capture_output=True)
    
    # Ensure .git directory is copied properly
    subprocess.run(["chmod", "-R", "755", repo_dir], check=True, capture_output=True)

    # Create exports directory
    exports_dir = tmp_path / "exports"
    exports_dir.mkdir()

    # Mock subprocess.run for git clone to use our temp repo
    def mock_clone(*args, **kwargs):
        nonlocal logger
        cmd = args[0] if args else kwargs.get("args", [])
        if cmd[0] == "git" and cmd[1] == "clone":
            # Copy our temp repo instead of actually cloning
            target = Path(cmd[-1])
            # Use shutil.copytree for reliable directory copying
            import shutil
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(repo_dir, target, symlinks=True)
            # Verify the .git directory exists
            if not (target / ".git").exists():
                logger.error(f".git directory not found in {target}")
                raise RuntimeError("Git repository not properly copied")
            logger.debug(f"Repository copied to {target}, .git directory verified")
        return MagicMock(returncode=0)

    with patch("subprocess.run", side_effect=mock_clone):
        # Create args namespace
        args = MagicMock()
        args.repo_url = "https://github.com/owner/repo.git"
        args.branch = None
        args.token = None
        args.format = "text"
        args.output_file = "test_export.txt"
        args.skip_remove = False
        args.subdir = None  # Explicitly set subdir to None
        args.repo_url_sub = None  # Explicitly set repo_url_sub to None

        # Test with default branch
        with patch("git2txt.EXPORTS_DIR", str(exports_dir)):
            clone_and_export(args)
            assert "Using default branch" in caplog.text

        # Test with explicit branch
        args.branch = "test-branch"
        with patch("git2txt.EXPORTS_DIR", str(exports_dir)):
            clone_and_export(args)
            assert f"Checked out branch: {args.branch}" in caplog.text

        # Test with subdirectory
        args.branch = None
        args.subdir = "subdir"
        with patch("git2txt.EXPORTS_DIR", str(exports_dir)):
            clone_and_export(args)
            assert "Exporting from subdirectory: subdir" in caplog.text

        # Test with invalid subdirectory
        args.subdir = "nonexistent"
        with patch("git2txt.EXPORTS_DIR", str(exports_dir)):
            with pytest.raises(SystemExit):
                clone_and_export(args)
            assert "Subdirectory nonexistent does not exist" in caplog.text

        # Reset to default for final verification
        args.subdir = None
        args.branch = None

        # Patch exports directory
        with patch("git2txt.EXPORTS_DIR", str(exports_dir)):
            clone_and_export(args)

        # Verify export file was created
        assert (exports_dir / "test_export.txt").exists()


def test_local_export(tmp_path, caplog):
    """Test local directory export."""
    import logging
    from git2txt import setup_logging

    setup_logging()
    caplog.set_level(logging.INFO)

    # Create a sample directory with files
    local_dir = tmp_path / "local_project"
    local_dir.mkdir()
    (local_dir / "test.py").write_text("print('test')")

    # Create exports directory
    exports_dir = tmp_path / "exports"
    exports_dir.mkdir()

    # Create args namespace
    args = MagicMock()
    args.local_dir = str(local_dir)
    args.format = "text"
    args.output_file = "test_export.txt"
    args.skip_remove = False

    # Patch exports directory and ensure it exists
    with patch("git2txt.EXPORTS_DIR", str(exports_dir)):
        # Add debug logging
        logger = logging.getLogger("git2txt")
        logger.setLevel(logging.DEBUG)
        local_export(args)
        
        # Log the expected output path
        expected_path = exports_dir / "test_export.txt"
        logger.debug(f"Expected output path: {expected_path}")
        logger.debug(f"Directory contents: {list(exports_dir.iterdir())}")
        
        # Wait a moment for file operations to complete
        import time
        time.sleep(0.1)

    # Verify export file was created
    assert (exports_dir / "test_export.txt").exists()

    # Verify export was logged
    assert any("Starting export of local directory" in record.message for record in caplog.records)


def test_branch_handling(tmp_path, caplog):
    """Test branch checkout behavior."""
    from argparse import Namespace
    import logging
    import subprocess
    
    caplog.set_level(logging.INFO)
    
    # Create a test repository
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "test.py").write_text("print('test')")
    
    # Initialize git repo
    subprocess.run(["git", "init", "--initial-branch=main"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True, capture_output=True)
    
    # Create and switch to test branch
    subprocess.run(["git", "checkout", "-b", "test-branch"], cwd=repo_dir, check=True, capture_output=True)
    (repo_dir / "branch-file.py").write_text("print('branch test')")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Branch commit"], cwd=repo_dir, check=True, capture_output=True)
    
    # Switch back to main
    subprocess.run(["git", "checkout", "main"], cwd=repo_dir, check=True, capture_output=True)
    
    # Create exports directory
    exports_dir = tmp_path / "exports"
    exports_dir.mkdir()
    
    # Mock subprocess.run for git clone
    def mock_clone(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        if cmd[0] == "git" and cmd[1] == "clone":
            target = Path(cmd[-1])
            import shutil
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(repo_dir, target, symlinks=True)
        return MagicMock(returncode=0)
    
    
    with patch("subprocess.run", side_effect=mock_clone):
        # Test default branch
        args = Namespace(
            repo_url="https://github.com/owner/repo.git",
            branch=None,
            token=None,
            output_file=str(tmp_path / "output.txt"),
            skip_remove=False,
            format="text",
            subdir=None,
            repo_url_sub=None
        )
        
        with patch("git2txt.EXPORTS_DIR", str(exports_dir)):
            clone_and_export(args)
            assert "Using default branch" in caplog.text
        
        # Test explicit branch
        args.branch = "test-branch"
        with patch("git2txt.EXPORTS_DIR", str(exports_dir)):
            clone_and_export(args)
            assert f"Checked out branch: {args.branch}" in caplog.text


def test_subdirectory_handling(tmp_path, caplog):
    """Test subdirectory export behavior."""
    from argparse import Namespace
    import logging
    import subprocess
    
    caplog.set_level(logging.INFO)
    
    # Create test repository
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    
    # Create main directory content
    (repo_dir / "main.py").write_text("print('main')")
    
    # Create subdirectory content
    subdir = repo_dir / "subdir"
    subdir.mkdir()
    (subdir / "sub.py").write_text("print('sub')")
    
    # Initialize git repo
    subprocess.run(["git", "init", "--initial-branch=main"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True, capture_output=True)
    
    # Create exports directory
    exports_dir = tmp_path / "exports"
    exports_dir.mkdir()
    
    # Mock subprocess.run for git clone
    def mock_clone(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        if cmd[0] == "git" and cmd[1] == "clone":
            target = Path(cmd[-1])
            import shutil
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(repo_dir, target, symlinks=True)
        return MagicMock(returncode=0)
    
    with patch("subprocess.run", side_effect=mock_clone):
        # Test with valid subdirectory
        args = Namespace(
            repo_url="https://github.com/owner/repo.git",  # Use GitHub URL to pass validation
            branch=None,
            token=None,
            output_file=str(tmp_path / "output.txt"),
            skip_remove=False,
            format="text",
            subdir="subdir",
            repo_url_sub=None
        )
        
        with patch("git2txt.EXPORTS_DIR", str(exports_dir)):
            clone_and_export(args)
            assert "Exporting from subdirectory: subdir" in caplog.text
        
        # Test with invalid subdirectory
        args.subdir = "nonexistent"
        with patch("git2txt.EXPORTS_DIR", str(exports_dir)):
            with pytest.raises(SystemExit):
                clone_and_export(args)
            assert "Subdirectory nonexistent does not exist" in caplog.text
        
        # Test without subdirectory
        args.subdir = None
        with patch("git2txt.EXPORTS_DIR", str(exports_dir)):
            clone_and_export(args)
            assert "Exporting from repository root" in caplog.text


def test_logging_setup(tmp_path, caplog):
    """Test logging setup and file handling."""
    import logging
    from git2txt import setup_logging, LOGS_DIR

    # Configure caplog
    caplog.set_level(logging.INFO)

    # Setup logging
    setup_logging()

    # Verify logs directory was created
    log_dir = Path(LOGS_DIR)
    assert log_dir.exists()
    assert log_dir.is_dir()

    # Test logging output
    logger = logging.getLogger("git2txt")
    test_message = "Test log message"
    logger.info(test_message)

    # Check if message was logged
    assert any(record.message == test_message for record in caplog.records)
