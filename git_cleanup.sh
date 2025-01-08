#!/bin/bash

# Source the test script to get access to logging functions and clean_git_artifacts
source "$(dirname "$0")/file2ai_test.sh"

# Run git cleanup
clean_git_artifacts

# Exit with the status of the last command
exit $?
