"""
levels.py
---------
Defines all log levels for logforge.

Standard 5:  DEBUG, INFO, WARNING, ERROR, CRITICAL
Custom 4:    AUDIT, WEBHOOK, SECURITY, DEPLOY

Each level has:
  - A numeric value (used for min_level comparisons in sinks)
  - A string name (used in formatted output)
  - A short label (used in terminal display, padded to 8 chars)
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LogLevel:
    """Represents a single log level."""
    name: str        # e.g. "ERROR"
    level_no: int    # e.g. 40
    label: str       # e.g. "ERROR   " — padded for aligned terminal output


# ── Level definitions ────────────────────────────────────────────────────────
#
# Numeric spacing is intentional:
#   - Gaps between levels leave room for future custom levels
#   - Custom levels slot naturally between standard ones
#
DEBUG    = LogLevel(name="DEBUG",    level_no=10, label="DEBUG   ")
INFO     = LogLevel(name="INFO",     level_no=20, label="INFO    ")
AUDIT    = LogLevel(name="AUDIT",    level_no=25, label="AUDIT   ")
WEBHOOK  = LogLevel(name="WEBHOOK",  level_no=28, label="WEBHOOK ")
WARNING  = LogLevel(name="WARNING",  level_no=30, label="WARNING ")
SECURITY = LogLevel(name="SECURITY", level_no=35, label="SECURITY")
ERROR    = LogLevel(name="ERROR",    level_no=40, label="ERROR   ")
DEPLOY   = LogLevel(name="DEPLOY",   level_no=45, label="DEPLOY  ")
CRITICAL = LogLevel(name="CRITICAL", level_no=50, label="CRITICAL")


# ── Registry ──────────────────────────────────────────────────────────────────
#
# A flat lookup dict so any part of the codebase can resolve a level
# by name (string) or numeric value without importing every constant.
#
ALL_LEVELS: dict[str, LogLevel] = {
    level.name: level
    for level in [
        DEBUG, INFO, AUDIT, WEBHOOK,
        WARNING, SECURITY, ERROR, DEPLOY, CRITICAL,
    ]
}

# Reverse lookup: level_no -> LogLevel
_LEVEL_BY_NUMBER: dict[int, LogLevel] = {
    level.level_no: level for level in ALL_LEVELS.values()
}


def get_level(identifier: str | int) -> LogLevel:
    """
    Resolve a LogLevel from either its name or numeric value.

    Examples:
        get_level("ERROR")    -> ERROR
        get_level(40)         -> ERROR
        get_level("audit")    -> AUDIT  (case-insensitive)

    Raises:
        ValueError if the identifier doesn't match any known level.
    """
    if isinstance(identifier, int):
        level = _LEVEL_BY_NUMBER.get(identifier)
        if level is None:
            raise ValueError(
                f"No log level with numeric value {identifier}. "
                f"Valid values: {sorted(_LEVEL_BY_NUMBER.keys())}"
            )
        return level

    if isinstance(identifier, str):
        level = ALL_LEVELS.get(identifier.upper())
        if level is None:
            raise ValueError(
                f"Unknown log level '{identifier}'. "
                f"Valid levels: {list(ALL_LEVELS.keys())}"
            )
        return level

    raise TypeError(
        f"identifier must be str or int, got {type(identifier).__name__}"
    )


def is_level_enabled(record_level_no: int, min_level_no: int) -> bool:
    """
    Returns True if a log record should pass through a sink
    based on that sink's minimum level threshold.

    Example:
        is_level_enabled(40, 30)  -> True   (ERROR >= WARNING)
        is_level_enabled(10, 30)  -> False  (DEBUG < WARNING)
    """
    return record_level_no >= min_level_no