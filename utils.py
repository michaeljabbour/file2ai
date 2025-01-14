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
    if not pattern_input or not pattern_input.strip():
        return False  # No patterns means no matches
        
    patterns = [p.strip() for p in pattern_input.split(';') if p.strip()]
    if not patterns:
        return False  # Empty patterns list means no matches
        
    # Ensure we have an absolute, normalized path
    try:
        path_obj = Path(file_path).resolve() if isinstance(file_path, str) else Path(file_path).resolve()
        # Convert to relative path for pattern matching
        try:
            path_obj = path_obj.relative_to(Path.cwd())
        except ValueError:
            # If path is not under cwd, use absolute path
            pass
        logger.debug(f"Normalized path for matching: {path_obj}")
    except Exception as e:
        logger.warning(f"Failed to normalize path {file_path}: {e}")
        return False
    
    # Handle patterns - convert glob patterns to proper format
    normalized_patterns = []
    for pattern in patterns:
        pattern = pattern.strip()
        if not pattern:
            continue
        # Remove any trailing slashes that might interfere with matching
        while pattern.endswith('/'):
            pattern = pattern[:-1]
        # Handle directory-specific patterns (e.g., build/*)
        if '/' in pattern:
            # Ensure pattern matches full path for directory patterns
            if not pattern.startswith('**/'):
                pattern = f'**/{pattern}'
        # Handle extension patterns (e.g., *.md)
        elif pattern.startswith('*.'):
            pattern = f'**/{pattern}'
        normalized_patterns.append(pattern)
        logger.debug(f"Normalized pattern: {pattern}")
    
    for pattern in normalized_patterns:
        try:
            if path_obj.match(pattern):
                logger.debug(f"Path {path_obj} matches pattern {pattern}")
                return True
            # Also try matching against the file name for extension patterns
            if pattern.startswith('*.') and path_obj.name.endswith(pattern[1:]):
                logger.debug(f"Path {path_obj} matches extension pattern {pattern}")
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
        
        # Handle symlinks and check existence
        try:
            if base_path.is_symlink():
                base_path = base_path.readlink().resolve()
            if not base_path.exists():
                raise IOError(f"Directory not found: {base_path}")
            if not base_path.is_dir():
                raise IOError(f"Not a directory: {base_path}")
        except (OSError, RuntimeError) as e:
            logger.error(f"Error accessing directory {base_path}: {e}")
            raise IOError(f"Error accessing directory {base_path}: {e}")
            
        logger.debug(f"Scanning directory: {base_path}")
        
        # Use os.walk for more reliable directory traversal
        for root, dirs, files in os.walk(str(base_path)):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for file in files:
                if file.startswith('.'):
                    continue
                    
                try:
                    file_path = Path(root) / file
                    abs_path = file_path.resolve()
                    
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
                    logger.debug(f"Pattern match result for {abs_path}: {matches} (mode: {pattern_mode})")
                    
                    # Include/exclude based on pattern_mode
                    if pattern_mode == "exclude" and matches:
                        logger.debug(f"Skipping {abs_path}: matches exclude pattern")
                        continue
                    elif pattern_mode == "include" and not matches and pattern_input.strip():
                        logger.debug(f"Skipping {abs_path}: doesn't match include pattern")
                        continue
                    
                    logger.debug(f"Including file {abs_path} (passed pattern filter)")
                        
                    filtered_files.append(str(abs_path))
                    logger.debug(f"Including file: {abs_path}")
                except (OSError, RuntimeError) as e:
                    logger.warning(f"Error processing file {file}: {e}")
                    continue
                    
        logger.info(f"Found {len(filtered_files)} files in {base_dir} after filtering")
    except Exception as e:
        logger.error(f"Error gathering files from {base_dir}: {e}")
        raise
        
    return sorted(filtered_files)
