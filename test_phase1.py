"""
test_phase1.py
--------------
Quick smoke tests for Phase 1 — levels.py and record.py.
Run with: python test_phase1.py
"""

import sys
sys.path.insert(0, ".")

from flowlog.levels import (
    DEBUG, INFO, AUDIT, WEBHOOK, WARNING,
    SECURITY, ERROR, DEPLOY, CRITICAL,
    get_level, is_level_enabled, ALL_LEVELS,
)
from flowlog.record import build_record

PASS = "✓"
FAIL = "✗"
errors = 0


def check(label: str, condition: bool):
    global errors
    if condition:
        print(f"  {PASS}  {label}")
    else:
        print(f"  {FAIL}  {label}  <-- FAILED")
        errors += 1


# ── Level ordering ────────────────────────────────────────────────────────────
print("\n── Level ordering ──")
check("DEBUG(10) < INFO(20)",       DEBUG.level_no    < INFO.level_no)
check("INFO(20) < AUDIT(25)",       INFO.level_no     < AUDIT.level_no)
check("AUDIT(25) < WEBHOOK(28)",    AUDIT.level_no    < WEBHOOK.level_no)
check("WEBHOOK(28) < WARNING(30)",  WEBHOOK.level_no  < WARNING.level_no)
check("WARNING(30) < SECURITY(35)", WARNING.level_no  < SECURITY.level_no)
check("SECURITY(35) < ERROR(40)",   SECURITY.level_no < ERROR.level_no)
check("ERROR(40) < DEPLOY(45)",     ERROR.level_no    < DEPLOY.level_no)
check("DEPLOY(45) < CRITICAL(50)",  DEPLOY.level_no   < CRITICAL.level_no)

# ── get_level ─────────────────────────────────────────────────────────────────
print("\n── get_level() ──")
check("get_level('ERROR') returns ERROR",        get_level("ERROR") == ERROR)
check("get_level('error') case-insensitive",     get_level("error") == ERROR)
check("get_level(40) returns ERROR",             get_level(40) == ERROR)
check("get_level('AUDIT') returns AUDIT",        get_level("AUDIT") == AUDIT)
check("get_level('SECURITY') returns SECURITY",  get_level("SECURITY") == SECURITY)
check("get_level('DEPLOY') returns DEPLOY",      get_level("DEPLOY") == DEPLOY)
check("get_level('WEBHOOK') returns WEBHOOK",    get_level("WEBHOOK") == WEBHOOK)

try:
    get_level("NONSENSE")
    check("get_level('NONSENSE') raises ValueError", False)
except ValueError:
    check("get_level('NONSENSE') raises ValueError", True)

try:
    get_level(999)
    check("get_level(999) raises ValueError", False)
except ValueError:
    check("get_level(999) raises ValueError", True)

# ── is_level_enabled ──────────────────────────────────────────────────────────
print("\n── is_level_enabled() ──")
check("ERROR(40) passes WARNING(30) gate",    is_level_enabled(40, 30))
check("CRITICAL(50) passes ERROR(40) gate",   is_level_enabled(50, 40))
check("DEBUG(10) blocked by WARNING(30) gate", not is_level_enabled(10, 30))
check("INFO(20) blocked by ERROR(40) gate",    not is_level_enabled(20, 40))
check("ERROR(40) passes exact ERROR(40) gate", is_level_enabled(40, 40))

# ── ALL_LEVELS registry ───────────────────────────────────────────────────────
print("\n── ALL_LEVELS registry ──")
check("Registry contains all 9 levels", len(ALL_LEVELS) == 9)
check("All expected level names present", all(
    name in ALL_LEVELS for name in
    ["DEBUG", "INFO", "AUDIT", "WEBHOOK", "WARNING", "SECURITY", "ERROR", "DEPLOY", "CRITICAL"]
))

# ── LogRecord ─────────────────────────────────────────────────────────────────
print("\n── LogRecord ──")
record = build_record(
    level_name  = "ERROR",
    level_no    = 40,
    message     = "Database connection lost",
    logger_name = "riff.inventory",
    module      = "inventory.py",
    func_name   = "update_listing",
    line_no     = 84,
    extra       = {"host": "db.riff.internal", "retry": 3},
)

check("level_name is 'ERROR'",           record.level_name == "ERROR")
check("level_no is 40",                  record.level_no == 40)
check("message is correct",              record.message == "Database connection lost")
check("logger_name is correct",          record.logger_name == "riff.inventory")
check("extra dict preserved",            record.extra["host"] == "db.riff.internal")
check("has_extra is True",               record.has_extra)
check("has_exception is False",          not record.has_exception)
check("timestamp_iso ends with Z",       record.timestamp_iso.endswith("Z"))
check("timestamp_human has spaces",      " " in record.timestamp_human)

d = record.to_dict()
check("to_dict() has 'level' key",       "level" in d)
check("to_dict() has 'extra' key",       "extra" in d)
check("to_dict() extra host correct",    d["extra"]["host"] == "db.riff.internal")
check("to_dict() no 'exception' key (none raised)", "exception" not in d)

# ── LogRecord with exception ──────────────────────────────────────────────────
print("\n── LogRecord with exception ──")
try:
    raise ConnectionError("Could not reach database")
except ConnectionError as e:
    exc_record = build_record(
        level_name="CRITICAL", level_no=50,
        message="DB down", logger_name="riff",
        module="db.py", func_name="connect", line_no=12,
        exc=e,
    )

check("has_exception is True",           exc_record.has_exception)
check("exc_info contains traceback",     "ConnectionError" in exc_record.exc_info)
check("to_dict() has 'exception' key",   "exception" in exc_record.to_dict())

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'─' * 40}")
if errors == 0:
    print(f"  All tests passed. Phase 1 is solid.\n")
else:
    print(f"  {errors} test(s) failed.\n")
    sys.exit(1)