# backend/app/core/auth.py
# Simple auth wrapper for compatibility
from app.core.security import get_current_user

__all__ = ['get_current_user']