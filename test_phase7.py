"""
test_phase7.py
--------------
Tests for Phase 7 — The Logger class.
Run with: python test_phase7.py
"""

import sys
import json
import tempfile
import threading
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, ".")

import flowlog
from flowlog import Logger
from flowlog.sinks.base import BaseSink
from flowlog.sinks.terminal import TerminalSink
from flowlog.sinks.file_sink import FileSink

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


# ── Capture sink for testing ──────────────────────────────────────────────────

class CaptureSink(BaseSink):
    def __init__(self, min_level=0):
        super().__init__(min_level=min_level, name="capture")
        self.received = []
    def emit(self, record):
        self.received.append(record)


# ── Package-level imports ─────────────────────────────────────────────────────
print("\n── Package imports ──")
check("Logger importable from flowlog",    hasattr(flowlog, "Logger"))
check("__version__ present",              hasattr(flowlog, "__version__"))
check("Level constants importable",       all(
    hasattr(flowlog, n) for n in
    ["DEBUG","INFO","AUDIT","WEBHOOK","WARNING","SECURITY","ERROR","DEPLOY","CRITICAL"]
))
check("get_level importable",             hasattr(flowlog, "get_level"))
check("FlowlogConfig importable",         hasattr(flowlog, "FlowlogConfig"))

# ── Zero-config instantiation ─────────────────────────────────────────────────
print("\n── Zero-config Logger ──")
log = Logger()
check("Logger instantiates with no args", log is not None)
check("Default name is 'flowlog'",        log.name == "flowlog")
check("Has at least terminal sink",       log.sink_count >= 1)
check("repr contains name",              "flowlog" in repr(log))
check("repr contains sink count",        "sinks=" in repr(log))

# ── Named logger ──────────────────────────────────────────────────────────────
print("\n── Named Logger ──")
log = Logger("riff.inventory")
check("Name set correctly",               log.name == "riff.inventory")
check("repr shows correct name",          "riff.inventory" in repr(log))

# ── All 9 level methods exist ─────────────────────────────────────────────────
print("\n── Level methods ──")
for method in ["debug","info","audit","webhook","warning","security","error","deploy","critical"]:
    check(f"log.{method}() exists", callable(getattr(log, method, None)))

# ── log() dynamic method ──────────────────────────────────────────────────────
print("\n── log() dynamic dispatch ──")
cap = CaptureSink()
log2 = Logger("test")
log2.add_sink(cap)

log2.log("ERROR",  "by name")
log2.log(40,       "by number")
log2.log("audit",  "case insensitive")

check("log() by level name",             cap.received[0].level_name == "ERROR")
check("log() by level number",           cap.received[1].level_name == "ERROR")
check("log() case insensitive",          cap.received[2].level_name == "AUDIT")

# ── LogRecord fields populated correctly ─────────────────────────────────────
print("\n── LogRecord field capture ──")
cap2 = CaptureSink()
log3 = Logger("riff")
log3.add_sink(cap2)

log3.error("Something broke", extra={"code": 500})
record = cap2.received[0]

check("level_name correct",              record.level_name == "ERROR")
check("level_no correct",               record.level_no == 40)
check("message correct",                record.message == "Something broke")
check("logger_name correct",            record.logger_name == "riff")
check("extra preserved",                record.extra.get("code") == 500)
check("module captured",                record.module.endswith(".py"))
check("func_name captured",             len(record.func_name) > 0)
check("line_no is positive int",        isinstance(record.line_no, int) and record.line_no > 0)
check("timestamp set",                  record.timestamp is not None)

# ── Exception capture ─────────────────────────────────────────────────────────
print("\n── Exception capture ──")
cap3 = CaptureSink()
log4 = Logger("test")
log4.add_sink(cap3)

try:
    raise ValueError("Intentional test error")
except ValueError as e:
    log4.error("Caught an error", exc=e)

exc_record = cap3.received[0]
check("has_exception is True",           exc_record.has_exception)
check("exc_info contains error type",    "ValueError" in exc_record.exc_info)
check("exc_info contains message",       "Intentional test error" in exc_record.exc_info)

# ── Inline config ─────────────────────────────────────────────────────────────
print("\n── Inline config ──")
log5 = Logger("configured", config={
    "sinks": {
        "terminal": {"min_level": "ERROR"},
    }
})
check("Inline config accepted",          log5 is not None)
check("Name from arg overrides config",  log5.name == "configured")

# ── JSON file config ──────────────────────────────────────────────────────────
print("\n── JSON file config ──")
with tempfile.TemporaryDirectory() as tmpdir:
    log_path = Path(tmpdir) / "app.log"
    cfg_path = Path(tmpdir) / "flowlog.json"
    cfg_path.write_text(json.dumps({
        "logger_name": "from-file",
        "sinks": {
            "terminal": {"enabled": False},
            "file_text": {
                "enabled": True,
                "path":    str(log_path),
                "min_level": "DEBUG",
            },
        }
    }), encoding="utf-8")

    log6 = Logger(config=str(cfg_path))
    log6.info("Written to file")
    log6.error("Also written to file")
    log6.shutdown()

    content = log_path.read_text(encoding="utf-8")
    check("Logger name from file config",    log6.name == "from-file")
    check("INFO written to file",            "Written to file" in content)
    check("ERROR written to file",           "Also written to file" in content)

# ── Severity gating end-to-end ────────────────────────────────────────────────
print("\n── Severity gating ──")
cap_warn = CaptureSink(min_level=30)
log7 = Logger("gated")
log7.add_sink(cap_warn)

log7.debug("should not appear")
log7.info("should not appear")
log7.warning("should appear")
log7.error("should appear")
log7.critical("should appear")

check("debug blocked by min_level=30",   not any(r.level_name == "DEBUG"   for r in cap_warn.received))
check("info blocked by min_level=30",    not any(r.level_name == "INFO"    for r in cap_warn.received))
check("warning passes min_level=30",     any(r.level_name == "WARNING"  for r in cap_warn.received))
check("error passes min_level=30",       any(r.level_name == "ERROR"    for r in cap_warn.received))
check("critical passes min_level=30",    any(r.level_name == "CRITICAL" for r in cap_warn.received))
check("exactly 3 records received",      len(cap_warn.received) == 3)

# ── add_sink / remove_sink at runtime ─────────────────────────────────────────
print("\n── Runtime sink management ──")
log8 = Logger("runtime", config={"sinks": {"terminal": {"enabled": False}}})
cap_rt = CaptureSink()
check("No sinks initially (terminal off)", log8.sink_count == 0)
log8.add_sink(cap_rt)
check("Sink added at runtime",           log8.sink_count == 1)
log8.info("test")
check("Message received after add",      len(cap_rt.received) == 1)
log8.remove_sink(cap_rt)
check("Sink removed at runtime",         log8.sink_count == 0)
log8.info("test 2")
check("No more messages after remove",   len(cap_rt.received) == 1)

# ── Context manager ───────────────────────────────────────────────────────────
print("\n── Context manager ──")
cap_ctx = CaptureSink()
with Logger("ctx", config={"sinks": {"terminal": {"enabled": False}}}) as log_ctx:
    log_ctx.add_sink(cap_ctx)
    log_ctx.info("inside context")
    check("Logs inside context manager",  len(cap_ctx.received) == 1)
check("Logger exited context manager cleanly", True)

# ── Live terminal output — all 9 levels ───────────────────────────────────────
print("\n── Live terminal output ──")
print("  (all 9 levels dispatched through a real Logger instance)\n")
live_log = Logger("flowlog.demo")
live_log.debug("Connecting to database")
live_log.info("Server started on port 8080")
live_log.audit("User 42 deleted listing 130099")
live_log.webhook("WooCommerce order received — order #5091")
live_log.warning("Response time above threshold")
live_log.security("Failed login attempt from 91.2.3.4")
live_log.error("Database query timed out", extra={"query": "SELECT * FROM listings", "timeout_ms": 5000})
live_log.deploy("v2.3.1 pushed to production", extra={"env": "production", "pushed_by": "harry"})

try:
    raise ConnectionError("Could not reach database host")
except ConnectionError as e:
    live_log.critical("System is down — immediate attention required", exc=e)

live_log.shutdown()
check("All 9 levels dispatched without crash", True)

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'─' * 40}")
if errors == 0:
    print("  All tests passed. Phase 7 is solid.\n")
else:
    print(f"  {errors} test(s) failed.\n")
    sys.exit(1)