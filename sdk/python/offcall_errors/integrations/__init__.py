"""
OffCall AI - Framework Integrations

Available integrations:
- Django: OffCallMiddleware
- Flask: OffCallFlask
- FastAPI: OffCallFastAPI
"""

from .django import OffCallMiddleware
from .flask import OffCallFlask
from .fastapi import OffCallFastAPI

__all__ = [
    "OffCallMiddleware",
    "OffCallFlask",
    "OffCallFastAPI",
]
