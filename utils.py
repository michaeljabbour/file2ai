"""Shared utility functions for file2ai."""
import os
import logging
import fnmatch
from pathlib import Path
from typing import List, Union, Optional

logger = logging.getLogger(__name__)

def matches_pattern(file_path: Union[str, Path], pattern_input: Optional[str], base_dir: Optional[Union[str, Path]] = None) -> bool:
    """Check if a file matches any of the provided patterns.
    
    Args:
        file_path: Path to the file to check (str or Path)
        pattern_input: Semicolon-separated list of glob patterns, or None
        base_dir: Optional base directory for relative path comparisons. If None, uses cwd()
        
    Returns:
        bool: True if file matches any pattern, False otherwise
        
    Raises:
        TypeError: If file_path is None
    """
    if file_path is None:
        raise TypeError("file_path cannot be None")
    if not pattern_input or not pattern_input.strip():
        return False  # No patterns means no matches
        
    # Split and clean patterns, removing empty ones
    patterns = [p.strip() for p in pattern_input.split(';') if p.strip()]
    if not patterns:
        return False  # Empty patterns list means no matches
        
    # Ensure we have an absolute, normalized path
    try:
        path_obj = Path(file_path).resolve() if isinstance(file_path, str) else Path(file_path).resolve()
        base_path = Path(base_dir).resolve() if base_dir else Path.cwd()
        
        # Convert to relative path for pattern matching
        try:
            # First try relative to provided base_dir or cwd
            path_obj = path_obj.relative_to(base_path)
            logger.debug(f"Using relative path from {base_path}: {path_obj}")
        except ValueError:
            # If not under base_dir, try parent directories up to root
            current = base_path
            found = False
            while len(current.parents) > 0:
                try:
                    path_obj = path_obj.relative_to(current)
                    found = True
                    logger.debug(f"Found relative path from {current}: {path_obj}")
                    break
                except ValueError:
                    current = current.parent
            
            if not found:
                # If still not found, use absolute path
                logger.debug(f"Using absolute path: {path_obj}")
                
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
            
        # Always add the original pattern
        normalized_patterns.append(pattern)
        
        # If pattern doesn't start with **/, add a **/ version
        if not pattern.startswith('**/'):
            normalized_patterns.append(f'**/{pattern}')
            
        # For directory patterns, also add **/ version
        if '/' in pattern and not pattern.endswith('/*'):
            normalized_patterns.append(f'{pattern}/*')
        logger.debug(f"Normalized pattern: {pattern}")
    
    # Convert path to string and get parts for matching
    try:
        path_str = str(path_obj)
        path_parts = path_obj.parts
        
        for pattern in normalized_patterns:
            try:
                # Convert all paths and pattern to lowercase for case-insensitive matching
                lower_path_str = path_str.lower()
                lower_path_name = path_obj.name.lower()
                lower_pattern = pattern.lower()
                lower_path_parts = [p.lower() for p in path_parts]

                # Handle all pattern types with fnmatch
                if lower_pattern.startswith('*.'):
                    # Extension pattern - match against filename
                    if fnmatch.fnmatch(lower_path_name, lower_pattern):
                        logger.debug(f"Path {path_obj} matches extension pattern {pattern}")
                        return True
                elif '/' in lower_pattern:
                    # Directory pattern - try full path match first
                    if fnmatch.fnmatch(lower_path_str, lower_pattern):
                        logger.debug(f"Path {path_obj} matches directory pattern {pattern}")
                        return True
                    # Then check if file is under matched directory
                    pattern_dir = lower_pattern.split('/')[0]
                    if pattern_dir in lower_path_parts:
                        dir_index = lower_path_parts.index(pattern_dir)
                        # Check if this is actually the directory we want
                        if dir_index < len(lower_path_parts):  # File is in or under the directory
                            logger.debug(f"Path {path_obj} is in or under directory {pattern_dir}")
                            return True
                elif '*' in pattern:
                    # Validate pattern format
                    if pattern.startswith('**') and not pattern.startswith('**/'):
                        logger.warning(f"Invalid pattern format: {pattern} (** must be followed by /)")
                        return False
                    
                    # Wildcard pattern - try matching against both full path and filename
                    if fnmatch.fnmatch(lower_path_str, lower_pattern) or fnmatch.fnmatch(lower_path_name, lower_pattern):
                        logger.debug(f"Path {path_obj} matches wildcard pattern {pattern}")
                        return True
                    # Also try matching against any part of the path
                    for part in lower_path_parts:
                        if fnmatch.fnmatch(part, lower_pattern):
                            logger.debug(f"Path {path_obj} matches wildcard pattern {pattern} at part {part}")
                            return True
                else:
                    # Simple pattern - match against full path and filename
                    if fnmatch.fnmatch(path_str, pattern) or fnmatch.fnmatch(path_obj.name, pattern):
                        logger.debug(f"Path {path_obj} matches simple pattern {pattern}")
                        return True
            except Exception as e:
                logger.warning(f"Error matching pattern '{pattern}' against '{path_obj}': {e}")
                continue
    except Exception as e:
        logger.warning(f"Failed to process path {path_obj}: {e}")
        return False
    
    logger.debug(f"Path {path_obj} does not match any patterns")
    return False

def gather_filtered_files(base_dir: str, pattern_mode: str, pattern_input: str) -> List[str]:
    """Gather files from a directory recursively, applying pattern filters.
    
    Args:
        base_dir: Base directory to scan
        pattern_mode: Either 'exclude' or 'include'
        pattern_input: Semicolon-separated list of glob patterns
        
    Returns:
        List[str]: List of filtered file paths
        
    Raises:
        ValueError: If pattern_mode is invalid
        IOError: If directory access fails
    """
    # Validate inputs
    if pattern_mode not in ["exclude", "include"]:
        raise ValueError(f"Invalid pattern_mode: {pattern_mode}. Must be 'exclude' or 'include'")
        
    filtered_files = []
    
    # Default ignore patterns for common directories and files
    default_ignores = [
        "venv/*", "__pycache__/*", "*.pyc",
        ".git/*", ".pytest_cache/*", "*.egg-info/*",
        ".tox/*", ".coverage", ".DS_Store",
        "node_modules/*", ".env/*", ".venv/*",
        ".idea/*", ".vscode/*", "build/*", "dist/*"
    ]
    
    try:
        # Handle path normalization carefully for temporary directories
        try:
            base_path = Path(base_dir)
            if base_path.is_symlink():
                base_path = base_path.readlink()
            # Use absolute path but don't resolve symlinks in parent directories
            if not base_path.is_absolute():
                base_path = base_path.absolute()
        except (OSError, RuntimeError) as e:
            logger.error(f"Error normalizing path {base_dir}: {e}")
            raise IOError(f"Error normalizing path {base_dir}: {e}")

        # Verify directory exists and is accessible
        if not base_path.exists():
            raise IOError(f"Directory not found: {base_path}")
        if not base_path.is_dir():
            raise IOError(f"Not a directory: {base_path}")
        if not os.access(str(base_path), os.R_OK):
            raise IOError(f"Directory not readable: {base_path}")

        logger.debug(f"Scanning directory: {base_path}")

        # Use os.walk for more reliable directory traversal
        for root, dirs, files in os.walk(str(base_path)):
            # Skip hidden and ignored directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and 
                      not any(matches_pattern(d, pattern) for pattern in default_ignores)]
            
            # Skip files in ignored directories
            if any(matches_pattern(root, pattern) for pattern in default_ignores):
                continue

            for file in files:
                if file.startswith('.'):
                    continue

                try:
                    file_path = Path(root) / file
                    # Use absolute path but don't resolve symlinks
                    abs_path = file_path.absolute()

                    # Size checks removed - no longer restricting file sizes

                    # Check pattern match using path relative to base directory
                    try:
                        rel_path = abs_path.relative_to(base_path)
                        # First check if file should be ignored by default patterns
                        if any(matches_pattern(str(rel_path), pattern) for pattern in default_ignores):
                            logger.debug(f"Skipping {rel_path}: matches default ignore pattern")
                            continue
                        
                        # Then check user-provided patterns
                        matches = matches_pattern(str(rel_path), pattern_input, base_dir=base_path)
                        logger.debug(f"Pattern match result for {rel_path}: {matches} (mode: {pattern_mode})")
                    except ValueError:
                        logger.warning(f"Could not determine relative path for {abs_path}")
                        continue

                    # Include/exclude based on pattern_mode
                    if pattern_mode == "exclude" and matches:
                        logger.debug(f"Skipping {abs_path}: matches exclude pattern")
                        continue
                    elif pattern_mode == "include" and not matches and pattern_input.strip():
                        logger.debug(f"Skipping {abs_path}: doesn't match include pattern")
                        continue

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
