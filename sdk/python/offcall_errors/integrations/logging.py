"""
OffCall AI - Python Logging Integration

Usage:
    import logging
    from offcall_errors.integrations.logging import OffCallHandler

    # Add to root logger
    logging.getLogger().addHandler(OffCallHandler(level=logging.ERROR))

    # Or to specific logger
    logger = logging.getLogger("myapp")
    logger.addHandler(OffCallHandler(level=logging.ERROR))
"""

import logging
from typing import Optional


class OffCallHandler(logging.Handler):
    """
    Logging handler that sends log records to OffCall.

    By default, only captures ERROR and above. Set level to customize.

    Args:
        level: Minimum log level to capture (default: ERROR)
        capture_exceptions: Also capture exception info (default: True)
    """

    def __init__(
        self,
        level: int = logging.ERROR,
        capture_exceptions: bool = True,
    ):
        super().__init__(level=level)
        self.capture_exceptions = capture_exceptions

    def emit(self, record: logging.LogRecord):
        """Emit a log record to OffCall."""
        try:
            import offcall_errors

            # Map logging levels to OffCall levels
            level_map = {
                logging.DEBUG: "debug",
                logging.INFO: "info",
                logging.WARNING: "warning",
                logging.ERROR: "error",
                logging.CRITICAL: "fatal",
            }
            level = level_map.get(record.levelno, "info")

            # Add breadcrumb for all log levels
            offcall_errors.add_breadcrumb(
                message=record.getMessage(),
                category="logging",
                type="default",
                level=level,
                data={
                    "logger": record.name,
                    "level": record.levelname,
                    "pathname": record.pathname,
                    "lineno": record.lineno,
                    "funcName": record.funcName,
                },
            )

            # Capture exception if present
            if self.capture_exceptions and record.exc_info:
                exc_type, exc_value, exc_tb = record.exc_info
                if exc_value:
                    offcall_errors.capture_exception(
                        exc_value,
                        extra={
                            "logger": record.name,
                            "log_message": record.getMessage(),
                        },
                    )
                    return

            # Capture message for ERROR and above without exception
            if record.levelno >= logging.ERROR:
                offcall_errors.capture_message(
                    record.getMessage(),
                    level=level,
                    extra={
                        "logger": record.name,
                        "pathname": record.pathname,
                        "lineno": record.lineno,
                        "funcName": record.funcName,
                    },
                )

        except Exception:
            # Don't let logging errors crash the application
            self.handleError(record)


class BreadcrumbHandler(logging.Handler):
    """
    Logging handler that only adds breadcrumbs (no error capture).

    Useful for adding log context to errors without sending logs as errors.

    Args:
        level: Minimum log level to capture (default: INFO)
    """

    def __init__(self, level: int = logging.INFO):
        super().__init__(level=level)

    def emit(self, record: logging.LogRecord):
        """Add log record as breadcrumb."""
        try:
            import offcall_errors

            level_map = {
                logging.DEBUG: "debug",
                logging.INFO: "info",
                logging.WARNING: "warning",
                logging.ERROR: "error",
                logging.CRITICAL: "fatal",
            }
            level = level_map.get(record.levelno, "info")

            offcall_errors.add_breadcrumb(
                message=record.getMessage(),
                category="logging",
                type="default",
                level=level,
                data={
                    "logger": record.name,
                    "level": record.levelname,
                },
            )

        except Exception:
            self.handleError(record)


def setup_logging(
    level: int = logging.ERROR,
    capture_exceptions: bool = True,
    breadcrumb_level: int = logging.INFO,
    logger_name: Optional[str] = None,
):
    """
    Convenience function to set up OffCall logging integration.

    Args:
        level: Level for error capture (default: ERROR)
        capture_exceptions: Capture exception info (default: True)
        breadcrumb_level: Level for breadcrumb capture (default: INFO)
        logger_name: Logger name, None for root logger (default: None)
    """
    logger = logging.getLogger(logger_name)

    # Add error handler
    error_handler = OffCallHandler(level=level, capture_exceptions=capture_exceptions)
    logger.addHandler(error_handler)

    # Add breadcrumb handler for lower levels
    if breadcrumb_level < level:
        breadcrumb_handler = BreadcrumbHandler(level=breadcrumb_level)
        logger.addHandler(breadcrumb_handler)

    return logger
