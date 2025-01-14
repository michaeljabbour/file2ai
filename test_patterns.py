#!/usr/bin/env python3
"""Test script to verify pattern filtering functionality."""
import os
from pathlib import Path
from utils import matches_pattern, gather_filtered_files
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def setup_test_directory(tmp_path):
    """Create a test directory structure with sample files."""
    # Create test files
    (tmp_path / "file1.txt").write_text("Test file 1")
    (tmp_path / "test.md").write_text("# Test markdown")
    
    # Create nested directories
    nested_dir = tmp_path / "nested"
    nested_dir.mkdir()
    (nested_dir / "file2.txt").write_text("Test file 2")
    
    deep_dir = nested_dir / "deep"
    deep_dir.mkdir()
    (deep_dir / "file3.txt").write_text("Test file 3")
    
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "artifact.txt").write_text("Build artifact")
    
    return tmp_path

def test_pattern_matching(tmp_path):
    """Test various pattern matching scenarios."""
    test_dir = setup_test_directory(tmp_path)
    
    # Test 1: Empty pattern (should match everything)
    logger.info("\nTest 1: Empty pattern")
    files = gather_filtered_files(str(test_dir), max_size_kb=100, pattern_mode="exclude", pattern_input="")
    logger.info(f"Found {len(files)} files with empty pattern")
    for f in files:
        logger.info(f"  {f}")
    assert len(files) > 0, "Empty pattern should match files"
    
    # Test 2: Exclude pattern
    logger.info("\nTest 2: Exclude pattern (*.md;build/*)")
    files = gather_filtered_files(str(test_dir), max_size_kb=100, pattern_mode="exclude", pattern_input="*.md;build/*")
    logger.info(f"Found {len(files)} files after excluding *.md and build/*")
    for f in files:
        logger.info(f"  {f}")
    assert not any("test.md" in str(f) for f in files), "Should exclude .md files"
    assert not any("build/" in str(f) for f in files), "Should exclude build directory"
    
    # Test 3: Include pattern
    logger.info("\nTest 3: Include pattern (*.txt)")
    files = gather_filtered_files(str(test_dir), max_size_kb=100, pattern_mode="include", pattern_input="*.txt")
    logger.info(f"Found {len(files)} .txt files")
    for f in files:
        logger.info(f"  {f}")
    assert all(".txt" in str(f) for f in files), "Should only include .txt files"
    assert len(files) == 3, "Should find exactly 3 .txt files"
    
    # Test 4: Complex include pattern
    logger.info("\nTest 4: Complex include pattern (file*.txt;subdir/*)")
    files = gather_filtered_files(str(test_dir), max_size_kb=100, pattern_mode="include", pattern_input="file*.txt;subdir/*")
    logger.info(f"Found {len(files)} files matching file*.txt or in subdir/")
    for f in files:
        logger.info(f"  {f}")
    assert any("file1.txt" in str(f) for f in files), "Should include file1.txt"
    assert any("file2.txt" in str(f) for f in files), "Should include file2.txt"
    
    # Test 5: Pattern with directory traversal
    logger.info("\nTest 5: Pattern with directory traversal (**/deep/*.txt)")
    files = gather_filtered_files(str(test_dir), max_size_kb=100, pattern_mode="include", pattern_input="**/deep/*.txt")
    logger.info(f"Found {len(files)} files in deep directory")
    for f in files:
        logger.info(f"  {f}")
    assert any("deep/file3.txt" in str(f) for f in files), "Should find file in deep directory"
    
    # Test 6: Size limit
    logger.info("\nTest 6: Size limit test")
    # Create a large file
    large_file = test_dir / "large.txt"
    large_file.write_text("x" * 200 * 1024)  # 200KB file
    files = gather_filtered_files(str(test_dir), max_size_kb=100, pattern_mode="exclude", pattern_input="")
    logger.info(f"Found {len(files)} files under size limit")
    assert not any("large.txt" in str(f) for f in files), "Should exclude files over size limit"
    
    # Test 7: Invalid patterns
    logger.info("\nTest 7: Invalid pattern test")
    files = gather_filtered_files(str(test_dir), max_size_kb=100, pattern_mode="exclude", pattern_input="[invalid")
    assert len(files) > 0, "Should handle invalid patterns gracefully"
    
    # Test 8: Symlink handling
    logger.info("\nTest 8: Symlink test")
    symlink_dir = test_dir / "symlink"
    symlink_dir.symlink_to(test_dir / "nested")
    files = gather_filtered_files(str(test_dir), max_size_kb=100, pattern_mode="include", pattern_input="**/file2.txt")
    assert any("nested/file2.txt" in str(f) for f in files), "Should handle symlinks correctly"
    
    # Test 9: Base directory handling
    logger.info("\nTest 9: Base directory test")
    files = gather_filtered_files(str(test_dir / "nested"), max_size_kb=100, pattern_mode="include", pattern_input="*.txt")
    assert len(files) == 2, "Should find files relative to base directory"
    assert all(str(test_dir / "nested") in str(f) for f in files), "Should use absolute paths"

def run_tests():
    """Run tests in standalone mode using temporary directory."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_pattern_matching(Path(tmp_dir))

if __name__ == "__main__":
    run_tests()
