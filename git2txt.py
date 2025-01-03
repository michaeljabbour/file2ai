#!/usr/bin/env python3
import sys
import warnings
from file2ai import main

warnings.warn(
    "'git2txt' is deprecated and will be removed in a future version. Please use 'file2ai' instead.",
    DeprecationWarning,
    stacklevel=2
)

if __name__ == "__main__":
    sys.exit(main())
