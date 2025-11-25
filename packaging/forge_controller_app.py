#!/usr/bin/env python3
"""
Buildly Forge Controller - Universal Launcher
Automatically detects platform and launches the appropriate controller
"""

import sys
import os
from pathlib import Path

# Ensure we can import from the package
sys.path.insert(0, str(Path(__file__).parent))

from forge_controller.core import get_platform, check_dependencies, install_dependencies


def main():
    """Main entry point - detects platform and launches appropriate controller"""
    platform = get_platform()
    
    print(f"Buildly Forge Controller")
    print(f"Platform: {platform}")
    print("=" * 40)
    
    # Check dependencies
    deps = check_dependencies()
    missing = [name for name, installed in deps.items() if not installed]
    
    if missing:
        print(f"\nMissing dependencies: {', '.join(missing)}")
        response = input("Install missing dependencies? [Y/n]: ").strip().lower()
        
        if response != 'n':
            print("\nInstalling dependencies...")
            install_dependencies()
            print("Dependencies installed. Please restart the application.")
            sys.exit(0)
        else:
            print("\nCannot run without dependencies.")
            sys.exit(1)
    
    print("\nStarting Forge Controller...")
    
    # Import and run platform-specific version
    if platform == 'macos':
        from forge_controller.macos_app import main as run_app
    elif platform == 'windows':
        from forge_controller.windows_app import main as run_app
    else:  # Linux
        from forge_controller.linux_app import main as run_app
    
    run_app()


if __name__ == '__main__':
    main()
