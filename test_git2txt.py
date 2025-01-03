import pytest
from pathlib import Path
import sys
from git2txt import parse_args, is_text_file, validate_github_url


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


def test_parse_args_interactive(mocker):
    """Test argument parsing with interactive input."""
    mocker.patch("builtins.input", side_effect=["https://github.com/owner/repo.git", ""])
    mocker.patch("sys.argv", ["git2txt.py"])  # Mock command line arguments
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
