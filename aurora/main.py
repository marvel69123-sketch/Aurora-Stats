"""
Aurora — Live football match statistics API
Entry point: uvicorn main:app --host 0.0.0.0 --port 8080
"""
from src.main import app  # re-export for uvicorn discovery

__all__ = ["app"]
