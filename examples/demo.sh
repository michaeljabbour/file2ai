#!/bin/bash

# Demo script for file2ai usage examples

echo "1. Export from local directory"
python ../file2ai.py --local-dir sample_project

echo -e "\n2. Export from a public GitHub repository"
python ../file2ai.py --repo-url https://github.com/pallets/flask.git

echo -e "\n3. Export from a specific branch of a repository"
python ../file2ai.py --repo-url https://github.com/pallets/flask.git --branch main

echo -e "\n4. Export from a private repository (requires token)"
echo "python ../file2ai.py --repo-url https://github.com/your-org/private-repo --token YOUR_TOKEN"

echo -e "\nNote: Exported files will be in the exports/ directory"
echo "Check the logs/ directory for detailed execution logs"
