#!/usr/bin/env python3
# Fix Ubuntu dependency conflicts for AutoCAD client
# Run: python3 fix_ubuntu_dependencies.py

import subprocess
import sys
import os
from pathlib import Path

def run_command(cmd, shell=False):
    """Run a command and return success status"""
    try:
        if shell:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        else:
            result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            return True, result.stdout
        else:
            return False, result.stderr
    except Exception as e:
        return False, str(e)

def main():
    print("="*60)
    print("Ubuntu AutoCAD Client - Dependency Fix")
    print("="*60)
    
    # Check if we're in a virtual environment
    in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    
    if not in_venv:
        print("\n⚠️  Not in a virtual environment!")
        print("It's recommended to use a virtual environment to avoid conflicts.")
        
        response = input("\nDo you want to create a virtual environment? (y/n): ").lower()
        
        if response == 'y':
            print("\nCreating virtual environment...")
            
            # Create venv
            success, output = run_command([sys.executable, "-m", "venv", "venv"])
            if not success:
                print(f"Failed to create venv: {output}")
                print("\nTrying with python3-venv package...")
                run_command(["sudo", "apt", "install", "-y", "python3-venv"])
                success, output = run_command([sys.executable, "-m", "venv", "venv"])
                
            if success:
                print("✓ Virtual environment created!")
                print("\nTo activate it, run:")
                print("  source venv/bin/activate")
                print("\nThen run this script again.")
                sys.exit(0)
            else:
                print("Failed to create virtual environment")
                print("Continuing with global installation...")
    
    print("\n" + "-"*40)
    print("Installing dependencies...")
    print("-"*40)
    
    # List of packages with specific versions
    packages = [
        ("httpx", "0.28.1"),
        ("websockets", "12.0"),
        ("rich", "13.9.4"),
    ]
    
    # First, uninstall conflicting versions
    print("\n1. Cleaning up old versions...")
    for package, _ in packages:
        print(f"   Removing {package}...")
        run_command([sys.executable, "-m", "pip", "uninstall", "-y", package])
    
    # Install specific versions
    print("\n2. Installing compatible versions...")
    for package, version in packages:
        print(f"   Installing {package}=={version}...")
        success, output = run_command([
            sys.executable, "-m", "pip", "install", f"{package}=={version}"
        ])
        
        if success:
            print(f"   ✓ {package} {version} installed")
        else:
            print(f"   ✗ Failed to install {package}: {output}")
    
    # Try to install asyncio (usually built-in)
    print("\n3. Checking asyncio...")
    try:
        import asyncio
        print("   ✓ asyncio is available (built-in)")
    except ImportError:
        print("   Installing asyncio...")
        run_command([sys.executable, "-m", "pip", "install", "asyncio"])
    
    # Verify installations
    print("\n" + "-"*40)
    print("Verifying installations...")
    print("-"*40)
    
    success, output = run_command([sys.executable, "-m", "pip", "list"])
    if success:
        for line in output.split('\n'):
            if any(pkg in line.lower() for pkg in ['httpx', 'websockets', 'rich', 'asyncio']):
                print(f"   {line.strip()}")
    
    # Test imports
    print("\n" + "-"*40)
    print("Testing imports...")
    print("-"*40)
    
    test_imports = [
        "httpx",
        "websockets",
        "rich",
        "asyncio"
    ]
    
    all_ok = True
    for module in test_imports:
        try:
            __import__(module)
            print(f"   ✓ {module} imported successfully")
        except ImportError as e:
            print(f"   ✗ Failed to import {module}: {e}")
            all_ok = False
    
    # Create a test script
    if all_ok:
        print("\n" + "="*60)
        print("✅ All dependencies installed successfully!")
        print("="*60)
        
        # Create test connection script
        test_script = '''#!/usr/bin/env python3
import asyncio
import httpx

async def test_connection():
    """Test connection to Windows AutoCAD server"""
    server_ip = input("Enter Windows server IP [192.168.1.193]: ").strip() or "192.168.1.193"
    
    print(f"\\nTesting connection to {server_ip}...")
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.get(f"http://{server_ip}:8000/health")
            if response.status_code == 200:
                data = response.json()
                print(f"✓ AutoCAD Server: {data}")
            else:
                print(f"✗ AutoCAD Server: HTTP {response.status_code}")
        except httpx.ConnectError:
            print(f"✗ Cannot connect to {server_ip}:8000")
            print("  Make sure the Windows server is running")
        except Exception as e:
            print(f"✗ Error: {e}")
        
        try:
            response = await client.get(f"http://{server_ip}:8001/health")
            if response.status_code == 200:
                data = response.json()
                print(f"✓ ETABS Server: {data}")
            else:
                print(f"✗ ETABS Server: HTTP {response.status_code}")
        except httpx.ConnectError:
            print(f"✗ Cannot connect to {server_ip}:8001")
        except Exception as e:
            print(f"✗ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())
'''
        
        with open('test_connection.py', 'w') as f:
            f.write(test_script)
        
        os.chmod('test_connection.py', 0o755)
        
        print("\nCreated test_connection.py")
        print("Run it to test connection to Windows server:")
        print("  python test_connection.py")
        
        print("\n" + "-"*40)
        print("Next steps:")
        print("-"*40)
        print("1. Make sure Windows servers are running")
        print("2. Test connection: python test_connection.py")
        print("3. Run client: python autocad_ubuntu_client.py")
        
    else:
        print("\n" + "="*60)
        print("⚠️  Some dependencies failed to install")
        print("="*60)
        print("\nTry creating a fresh virtual environment:")
        print("  python3 -m venv fresh_venv")
        print("  source fresh_venv/bin/activate")
        print("  python3 fix_ubuntu_dependencies.py")

if __name__ == "__main__":
    main()
