# backend/app/core/logging.py
# Simple logging wrapper for compatibility
import logging

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance"""
    return logging.getLogger(name)