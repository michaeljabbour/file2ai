#!/usr/bin/env python3
"""Test utility functions."""
import os
import pytest
from pathlib import Path
from utils import matches_pattern, gather_filtered_files
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_matches_pattern_basic():
    """Test basic pattern matching functionality."""
    # Test empty pattern
    assert not matches_pattern("test.txt", "")
    
    # Test exact match
    assert matches_pattern("test.txt", "*.txt")
    assert not matches_pattern("test.md", "*.txt")
    
    # Test multiple patterns
    assert matches_pattern("test.txt", "*.md;*.txt")
    assert matches_pattern("test.md", "*.md;*.txt")
    assert not matches_pattern("test.py", "*.md;*.txt")

def test_matches_pattern_directories():
    """Test directory pattern matching."""
    # Test directory patterns
    assert matches_pattern("build/test.txt", "build/*")
    assert matches_pattern("deep/nested/test.txt", "**/test.txt")
    assert not matches_pattern("src/test.txt", "build/*")
    
    # Test directory exclusion
    assert matches_pattern("node_modules/pkg/test.txt", "node_modules/**")
    assert not matches_pattern("src/pkg/test.txt", "node_modules/**")

def test_matches_pattern_base_dir(tmp_path):
    """Test pattern matching with base directory."""
    # Create test structure
    test_dir = tmp_path / "test_dir"
    test_dir.mkdir()
    (test_dir / "test.txt").write_text("test")
    (test_dir / "nested").mkdir()
    (test_dir / "nested/test.md").write_text("test")
    
    # Test relative paths
    assert matches_pattern(test_dir / "test.txt", "*.txt", base_dir=test_dir)
    assert matches_pattern(test_dir / "nested/test.md", "nested/*.md", base_dir=test_dir)
    
    # Test absolute paths
    abs_path = (test_dir / "test.txt").resolve()
    assert matches_pattern(abs_path, "*.txt", base_dir=test_dir)

def test_matches_pattern_edge_cases():
    """Test edge cases in pattern matching."""
    # Test None/empty inputs
    with pytest.raises(TypeError):
        matches_pattern(None, "*.txt")  # type: ignore
    assert not matches_pattern("test.txt", None)
    assert not matches_pattern("", "*.txt")
    assert not matches_pattern("test.txt", "")
    
    # Test invalid patterns
    assert not matches_pattern("test.txt", "[invalid")
    assert not matches_pattern("test.txt", "**.txt")
    
    # Test case sensitivity
    assert matches_pattern("TEST.TXT", "*.txt")
    assert matches_pattern("test.txt", "*.TXT")

def test_gather_filtered_files_basic(tmp_path):
    """Test basic file gathering functionality."""
    # Create test files
    (tmp_path / "test1.txt").write_text("test1")
    (tmp_path / "test2.txt").write_text("test2")
    (tmp_path / "test.md").write_text("test")
    
    # Test include mode
    files = gather_filtered_files(str(tmp_path), max_size_kb=100, 
                                pattern_mode="include", pattern_input="*.txt")
    assert len(files) == 2
    assert all(".txt" in f for f in files)
    
    # Test exclude mode
    files = gather_filtered_files(str(tmp_path), max_size_kb=100,
                                pattern_mode="exclude", pattern_input="*.md")
    assert len(files) == 2
    assert not any(".md" in f for f in files)

def test_gather_filtered_files_size_limit(tmp_path):
    """Test file size filtering."""
    # Create test files
    (tmp_path / "small.txt").write_text("small")
    (tmp_path / "large.txt").write_text("x" * 200 * 1024)  # 200KB
    
    # Test size limit
    files = gather_filtered_files(str(tmp_path), max_size_kb=100,
                                pattern_mode="include", pattern_input="*.txt")
    assert len(files) == 1
    assert "small.txt" in files[0]

def test_gather_filtered_files_symlinks(tmp_path):
    """Test symlink handling in file gathering."""
    # Create test structure
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "test.txt").write_text("test")
    
    link_dir = tmp_path / "link"
    link_dir.symlink_to(src_dir)
    
    # Test symlink traversal
    files = gather_filtered_files(str(link_dir), max_size_kb=100,
                                pattern_mode="include", pattern_input="*.txt")
    assert len(files) == 1
    assert "test.txt" in files[0]

def test_gather_filtered_files_errors():
    """Test error handling in file gathering."""
    # Test nonexistent directory
    with pytest.raises(IOError):
        gather_filtered_files("/nonexistent", max_size_kb=100,
                            pattern_mode="include", pattern_input="*.txt")
    
    # Test invalid pattern mode
    with pytest.raises(ValueError):
        gather_filtered_files(".", max_size_kb=100,
                            pattern_mode="invalid", pattern_input="*.txt")
    
    # Test negative size limit
    with pytest.raises(ValueError):
        gather_filtered_files(".", max_size_kb=-1,
                            pattern_mode="include", pattern_input="*.txt")
