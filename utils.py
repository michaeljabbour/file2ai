"""Shared utility functions for file2ai."""
import os
import logging
from pathlib import Path
from typing import List, Union

logger = logging.getLogger(__name__)

def matches_pattern(file_path: Union[str, Path], pattern_input: str) -> bool:
    """Check if a file matches any of the provided patterns.
    
    Args:
        file_path: Path to the file to check (str or Path)
        pattern_input: Semicolon-separated list of glob patterns
        
    Returns:
        bool: True if file matches any pattern, False otherwise
    """
    if not pattern_input:
        return False
        
    patterns = [p.strip() for p in pattern_input.split(';') if p.strip()]
    if not patterns:
        return False
        
    # Ensure we have an absolute, normalized path
    path_obj = Path(file_path).resolve() if isinstance(file_path, str) else Path(file_path).resolve()
    
    # Convert patterns to absolute paths if they look like absolute paths
    normalized_patterns = []
    for pattern in patterns:
        if pattern.startswith('/'):
            try:
                normalized_patterns.append(str(Path(pattern).resolve()))
            except Exception:
                normalized_patterns.append(pattern)
        else:
            normalized_patterns.append(pattern)
    
    for pattern in normalized_patterns:
        try:
            if path_obj.match(pattern):
                logger.debug(f"Path {path_obj} matches pattern {pattern}")
                return True
        except Exception as e:
            logger.warning(f"Error matching pattern '{pattern}' against '{path_obj}': {e}")
            continue
    
    logger.debug(f"Path {path_obj} does not match any patterns")
    return False

def gather_filtered_files(base_dir: str, max_size_kb: int, pattern_mode: str, pattern_input: str) -> List[str]:
    """Gather files from a directory recursively, applying size and pattern filters.
    
    Args:
        base_dir: Base directory to scan
        max_size_kb: Maximum file size in KB (files larger than this are excluded)
        pattern_mode: Either 'exclude' or 'include'
        pattern_input: Semicolon-separated list of glob patterns
        
    Returns:
        List[str]: List of filtered file paths
    """
    filtered_files = []
    max_size_bytes = max_size_kb * 1024
    
    try:
        # Ensure we have an absolute, normalized base path
        base_path = Path(base_dir).resolve()
        if not base_path.exists():
            raise IOError(f"Directory not found: {base_path}")
        if not base_path.is_dir():
            raise IOError(f"Not a directory: {base_path}")
            
        logger.debug(f"Scanning directory: {base_path}")
        
        for p in base_path.rglob('*'):
            if not p.is_file():
                continue
                
            # Skip hidden files and common ignore patterns
            if any(part.startswith('.') for part in p.parts):
                logger.debug(f"Skipping hidden file/directory: {p}")
                continue
                
            # Get absolute path
            abs_path = p.resolve()
            
            # Check file size
            try:
                size = abs_path.stat().st_size
                if size > max_size_bytes:
                    logger.debug(f"Skipping {abs_path}: exceeds size limit of {max_size_kb}KB ({size/1024:.1f}KB)")
                    continue
            except OSError as e:
                logger.warning(f"Error checking size of {abs_path}: {e}")
                continue
            
            # Check pattern match using absolute path
            matches = matches_pattern(abs_path, pattern_input)
            
            # Include/exclude based on pattern_mode
            if pattern_mode == "exclude" and matches:
                logger.debug(f"Skipping {abs_path}: matches exclude pattern")
                continue
            elif pattern_mode == "include" and not matches and pattern_input:
                logger.debug(f"Skipping {abs_path}: doesn't match include pattern")
                continue
                
            filtered_files.append(str(abs_path))
            logger.debug(f"Including file: {abs_path}")
                    
        logger.info(f"Found {len(filtered_files)} files in {base_dir} after filtering")
    except Exception as e:
        logger.error(f"Error gathering files from {base_dir}: {e}")
        raise
        
    return sorted(filtered_files)
