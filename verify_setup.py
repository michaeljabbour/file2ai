import sys
import importlib

required_packages = ['pytest', 'flask', 'file2ai']

def verify_imports():
    missing = []
    for package in required_packages:
        try:
            importlib.import_module(package)
            print(f"✓ {package} is installed")
        except ImportError:
            missing.append(package)
            print(f"✗ {package} is missing")
    
    if missing:
        print("\nMissing required packages:", ", ".join(missing))
        sys.exit(1)
    else:
        print("\nEnvironment setup complete - all required packages found")

if __name__ == "__main__":
    verify_imports()
