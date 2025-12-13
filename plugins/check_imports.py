# check_imports.py
import sys
import os

print("=== Checking Python Path ===")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")
print(f"Script directory: {os.path.dirname(os.path.abspath(__file__))}")

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("\n=== Checking Imports ===")

try:
    # Test basic imports
    import pyrogram
    print("✓ Pyrogram imported")
    
    from pyrogram import Client
    print("✓ Client imported")
    
    import pyrogram.utils
    print("✓ pyrogram.utils imported")
    
    pyrogram.utils.MIN_CHANNEL_ID = -1001896877147
    print("✓ MIN_CHANNEL_ID set")
    
except ImportError as e:
    print(f"✗ Import error: {e}")

print("\n=== Checking Config ===")
try:
    from config import Config
    print(f"✓ Config loaded")
    print(f"  API_ID: {Config.API_ID}")
    print(f"  ADMIN: {Config.ADMIN}")
except Exception as e:
    print(f"✗ Config error: {e}")

print("\n=== Checking Plugins ===")
plugins_dir = os.path.join(os.path.dirname(__file__), "plugins")
if os.path.exists(plugins_dir):
    print(f"Plugins folder exists: {plugins_dir}")
    print("Files in plugins:")
    for file in os.listdir(plugins_dir):
        if file.endswith('.py'):
            print(f"  - {file}")
else:
    print("✗ Plugins folder not found!")

print("\n=== Checking Helper ===")
helper_dir = os.path.join(os.path.dirname(__file__), "helper")
if os.path.exists(helper_dir):
    print(f"Helper folder exists: {helper_dir}")
    print("Files in helper:")
    for file in os.listdir(helper_dir):
        if file.endswith('.py'):
            print(f"  - {file}")
else:
    print("✗ Helper folder not found!")
