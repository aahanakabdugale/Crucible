import os
import pytest
from demo_sandbox.trial_3.app.config import AppConfig

def test_config_initialization():
    """
    Test case that verifies configuration loads successfully without crashing 
    on missing environment keys.
    """
    # Ensure the environment variable is intentionally missing to trigger the bug
    if "DATABASE_URL" in os.environ:
        del os.environ["DATABASE_URL"]
        
    config = AppConfig()
    
    # This will raise a KeyError due to unsafe os.environ lookup in config.py
    settings = config.load_database_url()
    
    assert settings["database_url"] is not None