#!/usr/bin/env python3
"""Test web interface functionality."""
import os
import pytest
from pathlib import Path
from web import app
import logging
import json

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@pytest.fixture
def client():
    """Create a test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_index_route(client):
    """Test index route returns frontend."""
    response = client.get('/')
    assert response.status_code == 200
    assert b'<!DOCTYPE html>' in response.data

def test_export_local_directory(client, tmp_path):
    """Test exporting local directory with pattern filtering."""
    # Create test files
    (tmp_path / "test.md").write_text("# Test markdown")
    (tmp_path / "test.txt").write_text("Test text")
    
    # Test include pattern
    data = {
        'command': 'export',
        'local_dir': str(tmp_path),
        'pattern_mode': 'include',
        'pattern_input': '*.md',
        'format': 'text'
    }
    response = client.post('/', data=data)
    assert response.status_code == 200
    result = json.loads(response.data)
    assert 'job_id' in result
    
    # Test exclude pattern
    data['pattern_mode'] = 'exclude'
    response = client.post('/', data=data)
    assert response.status_code == 200
    result = json.loads(response.data)
    assert 'job_id' in result

def test_convert_file(client, tmp_path):
    """Test file conversion endpoint."""
    # Create test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("Test content")
    
    # Test file conversion
    data = {
        'command': 'convert',
        'file': (test_file.open('rb'), 'test.txt'),
        'format': 'text'
    }
    response = client.post('/', data=data)
    assert response.status_code == 200
    result = json.loads(response.data)
    assert 'job_id' in result

def test_job_status(client):
    """Test job status endpoint."""
    response = client.get('/status/test-job-id')
    assert response.status_code == 404  # Job not found

def test_invalid_command(client):
    """Test invalid command handling."""
    data = {'command': 'invalid'}
    response = client.post('/', data=data)
    assert response.status_code == 400
    result = json.loads(response.data)
    assert 'error' in result

def test_missing_parameters(client):
    """Test missing parameter handling."""
    data = {'command': 'export'}  # Missing required parameters
    response = client.post('/', data=data)
    assert response.status_code == 400
    result = json.loads(response.data)
    assert 'error' in result
