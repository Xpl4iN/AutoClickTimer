import re
import os
import argparse

VERSION_FILE = os.path.join(os.path.dirname(__file__), '..', 'app', 'version.py')

def main():
    parser = argparse.ArgumentParser(description="Bump app/version.py")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--major", action="store_true", help="increment the major version")
    group.add_argument("--minor", action="store_true", help="increment the minor version")
    group.add_argument("--patch", action="store_true", help="increment the patch version")
    args = parser.parse_args()

    if not os.path.exists(VERSION_FILE):
        print(f"Error: {VERSION_FILE} not found.")
        return

    with open(VERSION_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the version string (e.g. VERSION = "1.1.2")
    match = re.search(r'VERSION\s*=\s*"(\d+)\.(\d+)\.(\d+)"', content)
    if not match:
        print("Error: Could not find VERSION string in app/version.py")
        return

    major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))
    if args.major:
        new_version = f'{major + 1}.0.0'
    elif args.minor:
        new_version = f'{major}.{minor + 1}.0'
    else:
        new_version = f'{major}.{minor}.{patch + 1}'

    # Replace the old version with the new version
    new_content = content.replace(f'VERSION = "{major}.{minor}.{patch}"', f'VERSION = "{new_version}"')

    with open(VERSION_FILE, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"Bumped version to {new_version}")

if __name__ == "__main__":
    main()
