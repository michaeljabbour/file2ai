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
        
    path_obj = Path(file_path) if isinstance(file_path, str) else file_path
    for pattern in patterns:
        try:
            if path_obj.match(pattern):
                return True
        except Exception as e:
            logger.warning(f"Error matching pattern '{pattern}' against '{path_obj}': {e}")
            continue
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
        base_path = Path(base_dir)
        if not base_path.exists():
            raise IOError(f"Directory not found: {base_dir}")
        if not base_path.is_dir():
            raise IOError(f"Not a directory: {base_dir}")
            
        for p in base_path.rglob('*'):
            if not p.is_file():
                continue
                
            # Skip hidden files and common ignore patterns
            if any(part.startswith('.') for part in p.parts):
                continue
                
            # Check file size
            try:
                if p.stat().st_size > max_size_bytes:
                    logger.debug(f"Skipping {p}: exceeds size limit of {max_size_kb}KB")
                    continue
            except OSError as e:
                logger.warning(f"Error checking size of {p}: {e}")
                continue
            
            # Check pattern match
            str_path = str(p.resolve())
            matches = matches_pattern(str_path, pattern_input)
            
            # Include/exclude based on pattern_mode
            if pattern_mode == "exclude" and matches:
                logger.debug(f"Skipping {p}: matches exclude pattern")
                continue
            elif pattern_mode == "include" and not matches and pattern_input:
                logger.debug(f"Skipping {p}: doesn't match include pattern")
                continue
                
            filtered_files.append(str_path)
                    
        logger.info(f"Found {len(filtered_files)} files in {base_dir} after filtering")
    except Exception as e:
        logger.error(f"Error gathering files from {base_dir}: {e}")
        raise
        
    return sorted(filtered_files)
