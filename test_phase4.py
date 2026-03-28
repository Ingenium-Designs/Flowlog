"""
test_phase4.py
--------------
Tests for Phase 4 — Dispatcher + background thread.
Run with: python test_phase4.py
"""

import sys
import time
import threading
from pathlib import Path
import tempfile

sys.path.insert(0, ".")

from flowlog.record import build_record
from flowlog.dispatcher import Dispatcher
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


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_record(level_name="INFO", level_no=20, message="Test message"):
    return build_record(
        level_name=level_name, level_no=level_no,
        message=message, logger_name="test",
        module="test.py", func_name="run", line_no=1,
    )


class CaptureSink(BaseSink):
    """Test sink that records every emit() call for inspection."""
    def __init__(self, min_level=0, name="capture"):
        super().__init__(min_level=min_level, name=name)
        self.received: list = []
        self.lock = threading.Lock()

    def emit(self, record):
        with self.lock:
            self.received.append(record)

    def wait_for(self, count: int, timeout: float = 2.0) -> bool:
        """Block until at least `count` records have been received."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self.lock:
                if len(self.received) >= count:
                    return True
            time.sleep(0.01)
        return False


# ── Dispatcher instantiation ──────────────────────────────────────────────────
print("\n── Dispatcher instantiation ──")
d = Dispatcher()
check("Dispatcher instantiates",           d is not None)
check("Starts with no sinks",              len(d.all_sinks) == 0)
check("Worker not running at start",       not d._running)

# ── Sync sink registration ────────────────────────────────────────────────────
print("\n── Sync sink registration ──")
d = Dispatcher()
sink_a = CaptureSink(name="a")
sink_b = CaptureSink(name="b", min_level=30)
d.add_sink(sink_a)
d.add_sink(sink_b)

check("Two sinks registered",              len(d.all_sinks) == 2)
check("Both in sync list",                 len(d._sync_sinks) == 2)
check("Async list still empty",            len(d._async_sinks) == 0)
check("Worker still not started",          not d._running)

# ── Sync dispatch ─────────────────────────────────────────────────────────────
print("\n── Sync dispatch ──")
info_record  = make_record("INFO",     20, "Info message")
error_record = make_record("ERROR",    40, "Error message")
debug_record = make_record("DEBUG",    10, "Debug message")

d.dispatch(info_record)
d.dispatch(error_record)
d.dispatch(debug_record)

check("sink_a (min=0) got 3 records",      len(sink_a.received) == 3)
check("sink_b (min=30) got 1 record",      len(sink_b.received) == 1)
check("sink_b got the ERROR record",       sink_b.received[0].level_name == "ERROR")
check("sink_a got INFO first",             sink_a.received[0].level_name == "INFO")

# ── Remove sink ───────────────────────────────────────────────────────────────
print("\n── Remove sink ──")
d.remove_sink(sink_b)
check("sink_b removed",                    len(d.all_sinks) == 1)
d.dispatch(error_record)
check("sink_b no longer receives after removal", len(sink_b.received) == 1)

# ── Disabled sink ─────────────────────────────────────────────────────────────
print("\n── Disabled sink ──")
d2 = Dispatcher()
cap = CaptureSink()
d2.add_sink(cap)
cap.disable()
d2.dispatch(info_record)
check("Disabled sink receives nothing",    len(cap.received) == 0)
cap.enable()
d2.dispatch(info_record)
check("Re-enabled sink receives again",    len(cap.received) == 1)

# ── Async sink ────────────────────────────────────────────────────────────────
print("\n── Async sink ──")
d3 = Dispatcher()
async_cap = CaptureSink(name="async-cap")
d3.add_sink(async_cap, asynchronous=True)

check("Worker thread started on async add", d3._running)
check("Async list has one sink",           len(d3._async_sinks) == 1)
check("Sync list still empty",             len(d3._sync_sinks) == 0)

d3.dispatch(info_record)
d3.dispatch(error_record)

received = async_cap.wait_for(2, timeout=2.0)
check("Async sink received both records",  received)
check("Async sink got INFO",               any(r.level_name == "INFO"  for r in async_cap.received))
check("Async sink got ERROR",              any(r.level_name == "ERROR" for r in async_cap.received))

# ── Mixed sync + async ────────────────────────────────────────────────────────
print("\n── Mixed sync + async ──")
d4 = Dispatcher()
sync_cap  = CaptureSink(name="sync")
async_cap2 = CaptureSink(name="async", min_level=30)
d4.add_sink(sync_cap,   asynchronous=False)
d4.add_sink(async_cap2, asynchronous=True)

d4.dispatch(info_record)
d4.dispatch(error_record)

# Sync sink should be immediate
check("Sync sink got 2 records immediately", len(sync_cap.received) == 2)

# Async sink needs a moment
async_cap2.wait_for(1, timeout=2.0)
check("Async sink (min=30) got 1 record",  len(async_cap2.received) == 1)
check("Async sink got ERROR not INFO",     async_cap2.received[0].level_name == "ERROR")

# ── Worker thread identity ────────────────────────────────────────────────────
print("\n── Worker thread ──")
check("Worker is a daemon thread",         d4._worker.daemon)
check("Worker is named flowlog-worker",    d4._worker.name == "flowlog-worker")
check("Worker is alive",                   d4._worker.is_alive())

# ── flush() ───────────────────────────────────────────────────────────────────
print("\n── flush() ──")
d5 = Dispatcher()
slow_cap = CaptureSink(name="slow")
d5.add_sink(slow_cap, asynchronous=True)

for i in range(10):
    d5.dispatch(make_record(message=f"message {i}"))

d5.flush()
check("flush() waits for all 10 records",  len(slow_cap.received) == 10)

# ── shutdown() ────────────────────────────────────────────────────────────────
print("\n── shutdown() ──")
d6 = Dispatcher()
shutdown_cap = CaptureSink(name="shutdown")
d6.add_sink(shutdown_cap, asynchronous=True)
d6.dispatch(info_record)
d6.flush()
d6.shutdown(timeout=2.0)
check("Worker stopped after shutdown",     not d6._worker.is_alive())
check("_running is False after shutdown",  not d6._running)

# ── Dispatcher with real sinks ────────────────────────────────────────────────
print("\n── Dispatcher with real sinks ──")
with tempfile.TemporaryDirectory() as tmpdir:
    log_path = Path(tmpdir) / "app.log"
    d7 = Dispatcher()
    d7.add_sink(TerminalSink(min_level=0))
    d7.add_sink(FileSink(log_path, fmt="text", min_level=0))

    print("\n  [Live output — dispatching all 9 levels:]")
    for level_name, level_no in [
        ("DEBUG",10),("INFO",20),("AUDIT",25),("WEBHOOK",28),
        ("WARNING",30),("SECURITY",35),("ERROR",40),("DEPLOY",45),("CRITICAL",50)
    ]:
        r = build_record(
            level_name=level_name, level_no=level_no,
            message=f"Dispatcher test — {level_name}",
            logger_name="flowlog.dispatcher", module="dispatcher.py",
            func_name="test", line_no=1,
        )
        d7.dispatch(r)

    content = log_path.read_text(encoding="utf-8")
    check("All 9 levels written to file",  content.count("Dispatcher test") == 9)
    d7.shutdown()

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'─' * 40}")
if errors == 0:
    print("  All tests passed. Phase 4 is solid.\n")
else:
    print(f"  {errors} test(s) failed.\n")
    sys.exit(1)