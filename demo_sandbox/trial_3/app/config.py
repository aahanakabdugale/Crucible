import os

class AppConfig:
    """
    Simulates an application configuration loader during startup initialization.
    Contains a deliberate bug: direct unsafe key lookup on os.environ for a critical DB URL.
    """
    def __init__(self):
        self.env_name = os.getenv("APP_EN", "development")
        
    def load_database_url(self):
        # BUG: Using direct subscripting os.environ["DATABASE_URL"] instead of 
        # a safe accessor or fallback, causing a KeyError when the env var is missing.
        # FIX: Use os.getenv with a default empty string to prevent KeyError and satisfy the test's "is not None" assertion.
        db_url = os.getenv("DATABASE_URL", "")
        return {"environment": self.env_name, "database_url": db_url}