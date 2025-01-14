#!/usr/bin/env python3
"""Test script to verify pattern filtering functionality."""
import os
from pathlib import Path
from utils import matches_pattern, gather_filtered_files
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_pattern_matching():
    """Test various pattern matching scenarios."""
    test_dir = Path("test_upload")
    
    # Test 1: Empty pattern (should match everything)
    logger.info("\nTest 1: Empty pattern")
    files = gather_filtered_files(str(test_dir), max_size_kb=100, pattern_mode="exclude", pattern_input="")
    logger.info(f"Found {len(files)} files with empty pattern")
    for f in files:
        logger.info(f"  {f}")
    
    # Test 2: Exclude pattern
    logger.info("\nTest 2: Exclude pattern (*.md;build/*)")
    files = gather_filtered_files(str(test_dir), max_size_kb=100, pattern_mode="exclude", pattern_input="*.md;build/*")
    logger.info(f"Found {len(files)} files after excluding *.md and build/*")
    for f in files:
        logger.info(f"  {f}")
    
    # Test 3: Include pattern
    logger.info("\nTest 3: Include pattern (*.txt)")
    files = gather_filtered_files(str(test_dir), max_size_kb=100, pattern_mode="include", pattern_input="*.txt")
    logger.info(f"Found {len(files)} .txt files")
    for f in files:
        logger.info(f"  {f}")
    
    # Test 4: Complex include pattern
    logger.info("\nTest 4: Complex include pattern (file*.txt;subdir/*)")
    files = gather_filtered_files(str(test_dir), max_size_kb=100, pattern_mode="include", pattern_input="file*.txt;subdir/*")
    logger.info(f"Found {len(files)} files matching file*.txt or in subdir/")
    for f in files:
        logger.info(f"  {f}")

if __name__ == "__main__":
    test_pattern_matching()
