#!/usr/bin/env python3
from file2ai import parse_github_url

def test_file2ai_extension():
    # Test 1: Basic URL without .git
    base_url, branch, subdir = parse_github_url('https://github.com/owner/repo')
    print(f'Test 1 - Basic URL: {base_url} (branch={branch}, subdir={subdir})')
    assert base_url == 'https://github.com/owner/repo.git'

    # Test 2: URL already ending with .git
    base_url, branch, subdir = parse_github_url('https://github.com/owner/repo.git')
    print(f'Test 2 - URL with .git: {base_url} (branch={branch}, subdir={subdir})')
    assert base_url == 'https://github.com/owner/repo.git'

    # Test 3: URL with invalid suffix
    base_url, branch, subdir = parse_github_url('https://github.com/owner/repo/pulls')
    print(f'Test 3 - URL with pulls: {base_url} (branch={branch}, subdir={subdir})')
    assert base_url == 'https://github.com/owner/repo.git'

    # Test 4: URL with tree/branch pattern
    base_url, branch, subdir = parse_github_url('https://github.com/owner/repo/tree/main/src')
    print(f'Test 4 - URL with tree: {base_url} (branch={branch}, subdir={subdir})')
    assert base_url == 'https://github.com/owner/repo.git'

if __name__ == '__main__':
    test_file2ai_extension()
