import pytest
import os


def test_project_structure():
    """Test that the basic project structure exists"""
    # Test that the main source directory exists
    assert os.path.isdir('src'), "src directory should exist"
    
    # Test that configuration example file exists
    assert os.path.isfile('config.example.yaml'), "config.example.yaml should exist"
    
    # Test that requirements file exists
    assert os.path.isfile('requirements.txt'), "requirements.txt should exist"


def test_version_import():
    """Test basic module imports"""
    # This is a minimal test to ensure the project can be imported
    try:
        # Just check if we can import from the core module
        from src.core import config
        assert True
    except ImportError:
        assert False, "Should be able to import from src.core module"


def test_environment():
    """Test basic environment setup"""
    # Ensure Python version is compatible
    import sys
    assert sys.version_info >= (3, 9), "Python version should be 3.9 or higher"