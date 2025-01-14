"""Test URL parsing and authentication functionality."""
import pytest
from file2ai import parse_github_url, build_auth_url

def test_parse_github_url_none():
    """Test parse_github_url with None input."""
    assert parse_github_url(None) == (None, None, None)
    assert parse_github_url("") == (None, None, None)

def test_parse_github_url_invalid():
    """Test parse_github_url with invalid URLs."""
    assert parse_github_url("not a url") == (None, None, None)
    assert parse_github_url("http://not-github.com/user/repo") == (None, None, None)

def test_parse_github_url_valid():
    """Test parse_github_url with valid URLs."""
    url = "https://github.com/user/repo"
    assert parse_github_url(url) == (url + ".git", None, None)

def test_parse_github_url_with_branch():
    """Test parse_github_url with branch."""
    url = "https://github.com/user/repo/tree/main"
    assert parse_github_url(url) == ("https://github.com/user/repo.git", "main", None)

def test_parse_github_url_with_subdir():
    """Test parse_github_url with subdirectory."""
    url = "https://github.com/user/repo/tree/main/src"
    assert parse_github_url(url, use_subdirectory=True) == (
        "https://github.com/user/repo.git",
        "main",
        "src"
    )

def test_parse_github_url_with_special_suffixes():
    """Test parse_github_url with special suffixes."""
    base = "https://github.com/user/repo"
    suffixes = ["/pulls", "/issues", "/actions", "/wiki"]
    for suffix in suffixes:
        assert parse_github_url(base + suffix) == (base + ".git", None, None)

def test_parse_github_url_with_whitespace():
    """Test parse_github_url with whitespace in branch name."""
    url = "https://github.com/user/repo/tree/feature branch"
    assert parse_github_url(url) == (
        "https://github.com/user/repo.git",
        "featurebranch",
        None
    )

def test_parse_github_url_without_protocol():
    """Test parse_github_url without http(s):// prefix."""
    url = "github.com/user/repo"
    assert parse_github_url(url) == ("https://github.com/user/repo.git", None, None)

def test_parse_github_url_complex():
    """Test parse_github_url with complex URL."""
    url = "https://github.com/user/repo/tree/feature/src/lib?query=1#hash"
    assert parse_github_url(url, use_subdirectory=True) == (
        "https://github.com/user/repo.git",
        "feature",
        "src/lib"
    )

def test_build_auth_url_none():
    """Test build_auth_url with None inputs."""
    assert build_auth_url(None, "token") is None
    assert build_auth_url("https://github.com/user/repo", None) is None
    assert build_auth_url(None, None) is None

def test_build_auth_url_valid():
    """Test build_auth_url with valid inputs."""
    url = "https://github.com/user/repo"
    token = "abc123"
    assert build_auth_url(url, token) == f"https://{token}@github.com/user/repo"

def test_build_auth_url_http():
    """Test build_auth_url with HTTP URL."""
    url = "http://github.com/user/repo"
    token = "abc123"
    assert build_auth_url(url, token) == f"https://{token}@github.com/user/repo"
