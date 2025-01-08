import logging
import pytest

@pytest.fixture(autouse=True)
def setup_logging(caplog):
    """Configure logging for all tests."""
    # Configure caplog first
    caplog.set_level(logging.DEBUG)
    
    # Get the root logger and file2ai logger
    root_logger = logging.getLogger()
    file2ai_logger = logging.getLogger("file2ai")
    
    # Store original settings
    original_root_level = root_logger.level
    original_file2ai_level = file2ai_logger.level
    original_root_handlers = root_logger.handlers[:]
    original_file2ai_handlers = file2ai_logger.handlers[:]
    original_root_propagate = root_logger.propagate
    original_file2ai_propagate = file2ai_logger.propagate
    
    # Clear all handlers
    root_logger.handlers.clear()
    file2ai_logger.handlers.clear()
    
    # Configure loggers
    root_logger.setLevel(logging.DEBUG)
    file2ai_logger.setLevel(logging.DEBUG)
    root_logger.propagate = True
    file2ai_logger.propagate = True
    
    yield
    
    # Restore original settings
    root_logger.setLevel(original_root_level)
    file2ai_logger.setLevel(original_file2ai_level)
    root_logger.handlers = original_root_handlers
    file2ai_logger.handlers = original_file2ai_handlers
    root_logger.propagate = original_root_propagate
    file2ai_logger.propagate = original_file2ai_propagate
