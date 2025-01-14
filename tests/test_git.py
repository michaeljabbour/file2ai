"""Test git repository handling functionality."""
import os
import pytest
from pathlib import Path
from git import Repo, exc
import logging
from file2ai import clone_and_export, parse_github_url
from argparse import Namespace

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_branch_handling(tmp_path, caplog):
    """Test branch name sanitization and fallback behavior."""
    # Create test args with problematic branch name
    args = Namespace(
        repo_url="https://github.com/andrewyng/aisuite",
        branch="mainHEAD",
        token=None,
        output=str(tmp_path / "output.txt"),
        format="text",
        repo_url_sub=None,
        output_file=None,
        skip_remove=False,
        subdir=""
    )
    
    # Run export and check logs
    try:
        clone_and_export(args)
        # Check that mainHEAD was sanitized
        assert any("Invalid branch name format: mainHEAD" in record.message 
                  for record in caplog.records), "Should warn about invalid branch name"
        assert any("Checked out branch: main" in record.message 
                  for record in caplog.records), "Should fall back to main branch"
    except Exception as e:
        pytest.fail(f"Export failed: {e}")

def test_url_parsing():
    """Test GitHub URL parsing with various formats."""
    test_cases = [
        (
            "https://github.com/user/repo/tree/mainHEAD",
            ("https://github.com/user/repo.git", "main", None)
        ),
        (
            "https://github.com/user/repo/tree/feature-branch/subdir",
            ("https://github.com/user/repo.git", "feature-branch", "subdir")
        ),
        (
            "https://github.com/user/repo.git",
            ("https://github.com/user/repo.git", None, None)
        )
    ]
    
    for url, expected in test_cases:
        clone_url, branch, subdir = parse_github_url(url, use_subdirectory=True)
        assert (clone_url, branch, subdir) == expected, \
            f"URL parsing failed for {url}"
