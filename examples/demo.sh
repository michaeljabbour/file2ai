#!/bin/bash

# Demo script for git2txt usage examples

echo "1. Export from local directory"
python ../git2txt.py --local-dir sample_project

echo -e "\n2. Export from a public GitHub repository"
python ../git2txt.py --repo-url https://github.com/pallets/flask

echo -e "\n3. Export from a specific branch of a repository"
python ../git2txt.py --repo-url https://github.com/pallets/flask --branch main

echo -e "\n4. Export from a private repository (requires token)"
echo "python ../git2txt.py --repo-url https://github.com/your-org/private-repo --token YOUR_TOKEN"

echo -e "\nNote: Exported files will be in the exports/ directory"
echo "Check the logs/ directory for detailed execution logs"
