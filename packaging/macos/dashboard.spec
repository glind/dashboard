"""
PyInstaller spec file for Personal Dashboard macOS App
=====================================================
"""

# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

block_cipher = None

# Get the app directory
dashboard_root_env = os.environ.get('DASHBOARD_ROOT')
if dashboard_root_env:
    app_dir = Path(dashboard_root_env)
else:
    app_dir = Path.cwd().parent.parent  # Go up from packaging/macos to dashboard root

src_dir = app_dir / "src"

print(f"Building from dashboard root: {app_dir}")
print(f"Source directory: {src_dir}")

# Collect all Python files from src directory
src_files = []
for py_file in src_dir.rglob("*.py"):
    relative_path = py_file.relative_to(src_dir)
    src_files.append((str(py_file), str(relative_path.parent) if relative_path.parent != Path('.') else '.'))

# Collect data files
data_files = []
potential_files = [
    ('config/config.yaml.example', 'config/'),
    ('config/credentials.yaml.example', 'config/'),
    ('.env.example', '.'),
    ('README.md', '.'),
]

for src_path, dest_dir in potential_files:
    full_path = app_dir / src_path
    if full_path.exists():
        data_files.append((str(full_path), dest_dir))
    else:
        print(f"Warning: {full_path} not found, skipping")

# Add static files
static_dir = src_dir / "static"
if static_dir.exists():
    for static_file in static_dir.rglob("*"):
        if static_file.is_file():
            relative_path = static_file.relative_to(src_dir)
            data_files.append((str(static_file), str(relative_path.parent)))

# Add template files
templates_dir = src_dir / "templates"
if templates_dir.exists():
    for template_file in templates_dir.rglob("*"):
        if template_file.is_file():
            relative_path = template_file.relative_to(src_dir)
            data_files.append((str(template_file), str(relative_path.parent)))

a = Analysis(
    [str(app_dir / 'packaging/macos/app_main.py')],
    pathex=[str(app_dir), str(src_dir)],
    binaries=[],
    datas=data_files + src_files,
    hiddenimports=[
        # Core FastAPI and server dependencies
        'uvicorn',
        'uvicorn.main',
        'uvicorn.config',
        'uvicorn.server',
        'fastapi',
        'fastapi.staticfiles',
        'fastapi.templating',
        'fastapi.responses',
        'fastapi.middleware',
        'fastapi.middleware.cors',
        'starlette',
        'starlette.responses',
        'starlette.staticfiles',
        'starlette.templating',
        'starlette.middleware',
        'starlette.middleware.cors',
        'pydantic',
        'pydantic.fields',
        'pydantic.types',
        
        # Database and data handling
        'sqlite3',
        'sqlalchemy',
        'pathlib',
        'datetime',
        'typing',
        'logging',
        'json',
        'os',
        'sys',
        'subprocess',
        'threading',
        'time',
        'socket',
        'webbrowser',
        'urllib',
        'urllib.request',
        'urllib.error',
        
        # Web interface dependencies
        'webview',
        'jinja2',
        'jinja2.loaders',
        'markupsafe',
        
        # Google API dependencies
        'google.auth',
        'google.auth.transport.requests',
        'google_auth_oauthlib',
        'google_auth_oauthlib.flow',
        'googleapiclient',
        'googleapiclient.discovery',
        'googleapiclient.errors',
        
        # HTTP and networking
        'requests',
        'requests.auth',
        'requests.adapters',
        'httpx',
        'urllib3',
        
        # Configuration and serialization
        'yaml',
        'toml',
        'configparser',
        
        # Email handling
        'email',
        'email.mime',
        'email.mime.text',
        'email.mime.multipart',
        'imaplib',
        'poplib',
        'smtplib',
        
        # Data processing
        'pandas',
        'numpy',
        'matplotlib',
        'matplotlib.pyplot',
        
        # Collector modules
        'collectors',
        'collectors.base_collector',
        'collectors.gmail_collector',
        'collectors.calendar_collector',
        'collectors.github_collector',
        'collectors.news_collector',
        'collectors.weather_collector',
        'collectors.ticktick_collector',
        'collectors.music_collector',
        'collectors.network_collector',
        'collectors.vanity_alerts_collector',
        'collectors.jokes_collector',
        'collectors.notes_collector',
        # Processor modules
        'processors',
        'processors.data_processor',
        'processors.insight_generator',
        'processors.kpi_calculator',
        'processors.email_analyzer',
        'processors.ai_providers',
        'processors.ollama_analyzer',
        'processors.ai_training_collector',
        # Config and database
        'config',
        'config.settings',
        'database',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Personal Dashboard',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Set to False for windowed app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path here if you have one
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Personal Dashboard',
)

app = BUNDLE(
    coll,
    name='Personal Dashboard.app',
    icon=None,  # Add icon path here if you have one
    bundle_identifier='com.greglind.personal-dashboard',
    version='1.0.0',
    info_plist={
        'CFBundleDisplayName': 'Personal Dashboard',
        'CFBundleExecutable': 'Personal Dashboard',
        'CFBundleIdentifier': 'com.greglind.personal-dashboard',
        'CFBundleName': 'Personal Dashboard',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHumanReadableCopyright': 'Copyright © 2025 Greg Lind. All rights reserved.',
        'NSHighResolutionCapable': True,
        'LSBackgroundOnly': False,
        'NSRequiresAquaSystemAppearance': False,
    },
)