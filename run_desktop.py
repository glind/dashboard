#!/usr/bin/env python3
"""
Test runner for desktop app - runs without building
Quick way to test the desktop version during development
"""

import subprocess
import sys

print("""
╔══════════════════════════════════════════╗
║   Personal Dashboard - Desktop Test      ║
║                                          ║
║  Running in development mode...          ║
╚══════════════════════════════════════════╝
""")

# Check if pywebview is installed
try:
    import webview
    print("✅ pywebview is installed")
except ImportError:
    print("⚠️  pywebview not installed. Installing...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pywebview"])
    print("✅ pywebview installed")

# Run the desktop app
print("\n🚀 Starting desktop application...\n")
subprocess.run([sys.executable, "app_desktop.py"])
