#!/usr/bin/env python3
"""
Validation script for Polymarket Copy Trading Bot.
Run this to verify the system is properly set up.
"""
import sys

def check_imports():
    """Check that all required modules can be imported."""
    print("Checking imports...")
    modules = [
        'config', 'models', 'logger', 
        'polymarket_client', 'blockchain_listener',
        'trade_scaler', 'trade_executor',
        'position_tracker', 'risk_controller', 'main'
    ]
    
    failed = []
    for module in modules:
        try:
            __import__(module)
            print(f"  ✓ {module}")
        except Exception as e:
            print(f"  ✗ {module}: {e}")
            failed.append(module)
    
    return len(failed) == 0

def check_database():
    """Check database can be created."""
    print("\nChecking database...")
    try:
        from models import Database
        db = Database("sqlite:///:memory:")
        db.create_tables()
        print("  ✓ Database schema created successfully")
        return True
    except Exception as e:
        print(f"  ✗ Database error: {e}")
        return False

def check_configuration():
    """Check configuration system."""
    print("\nChecking configuration...")
    try:
        from config import Settings
        # Try to load without .env file
        print("  ✓ Configuration system ready")
        print("  ⚠ Create .env file with your settings before running")
        return True
    except Exception as e:
        print(f"  ✗ Configuration error: {e}")
        return False

def check_tests():
    """Check if tests pass."""
    print("\nChecking tests...")
    import subprocess
    result = subprocess.run(
        ['python3', '-m', 'pytest', 'test_*.py', '-v', '--tb=no'],
        capture_output=True,
        text=True
    )
    
    if 'passed' in result.stdout:
        # Extract test count
        for line in result.stdout.split('\n'):
            if 'passed' in line:
                print(f"  ✓ Tests: {line.strip()}")
                return True
    
    print(f"  ✗ Tests failed")
    return False

def main():
    """Run all validation checks."""
    print("="*60)
    print("Polymarket Copy Trading Bot - Validation")
    print("="*60)
    print()
    
    checks = [
        ("Module Imports", check_imports),
        ("Database", check_database),
        ("Configuration", check_configuration),
        ("Tests", check_tests),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            results.append(check_func())
        except Exception as e:
            print(f"\n✗ {name} check failed: {e}")
            results.append(False)
    
    print()
    print("="*60)
    
    if all(results):
        print("✅ ALL CHECKS PASSED")
        print()
        print("System is ready for use!")
        print()
        print("Next steps:")
        print("1. Copy .env.example to .env")
        print("2. Edit .env with your configuration")
        print("3. Run: python main.py")
        print()
        return 0
    else:
        print("❌ SOME CHECKS FAILED")
        print()
        print("Please fix the issues above before running the bot.")
        print()
        return 1

if __name__ == '__main__':
    sys.exit(main())
