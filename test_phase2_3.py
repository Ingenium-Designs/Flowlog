"""
test_phase2_3.py
----------------
Tests for Phase 2 (formatters) and Phase 3 (sinks).
Run with: python test_phase2_3.py
"""

import sys
import json
import csv
import tempfile
import os
from pathlib import Path

sys.path.insert(0, ".")

from flowlog.record import build_record
from flowlog.formatters import text, json_fmt, csv_fmt, markdown
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


# ── Shared test records ───────────────────────────────────────────────────────

basic = build_record(
    level_name="INFO", level_no=20, message="Server started",
    logger_name="myapp", module="app.py", func_name="main", line_no=10,
)

rich_record = build_record(
    level_name="ERROR", level_no=40, message="Database connection lost",
    logger_name="riff.inventory", module="inventory.py",
    func_name="update_listing", line_no=84,
    extra={"host": "db.riff.internal", "retry": 3},
)

try:
    raise ConnectionError("Could not reach database")
except ConnectionError as e:
    exc_record = build_record(
        level_name="CRITICAL", level_no=50, message="DB down",
        logger_name="riff", module="db.py", func_name="connect", line_no=12,
        exc=e,
    )

# ── Text formatter ────────────────────────────────────────────────────────────
print("\n── Text formatter ──")
t_basic = text.format(basic)
t_rich  = text.format(rich_record)
t_exc   = text.format(exc_record)

check("Contains timestamp",           "2026" in t_basic or "202" in t_basic)
check("Contains level name",          "INFO" in t_basic)
check("Contains logger name",         "myapp" in t_basic)
check("Contains message",             "Server started" in t_basic)
check("Contains module (location)",   "app.py" in t_basic)
check("Contains extra when present",  '"host"' in t_rich)
check("Contains exception info",      "ConnectionError" in t_exc)
check("No location with flag off",    "app.py" not in text.format(basic, include_location=False))

# ── JSON formatter ────────────────────────────────────────────────────────────
print("\n── JSON formatter ──")
j_compact = json_fmt.format(basic)
j_pretty  = json_fmt.format(rich_record, pretty=True)

parsed_compact = json.loads(j_compact)
parsed_pretty  = json.loads(j_pretty)

check("Compact is valid JSON",         isinstance(parsed_compact, dict))
check("Pretty is valid JSON",          isinstance(parsed_pretty, dict))
check("Has 'level' key",               "level" in parsed_compact)
check("Has 'message' key",             "message" in parsed_compact)
check("Has 'timestamp' key",           "timestamp" in parsed_compact)
check("Timestamp ends with Z",         parsed_compact["timestamp"].endswith("Z"))
check("Extra present in rich record",  "extra" in parsed_pretty)
check("Extra host correct",            parsed_pretty["extra"]["host"] == "db.riff.internal")
check("No extra in basic record",      "extra" not in parsed_compact)
check("Compact is one line",           "\n" not in j_compact)
check("Pretty has newlines",           "\n" in j_pretty)

# ── CSV formatter ─────────────────────────────────────────────────────────────
print("\n── CSV formatter ──")
header = csv_fmt.header_row()
row    = csv_fmt.format(rich_record)

header_cols = next(csv.reader([header]))
row_cols    = next(csv.reader([row]))

check("Header has 10 columns",              len(header_cols) == 10)
check("Data row has 10 columns",            len(row_cols) == 10)
check("Header starts with 'timestamp'",     header_cols[0] == "timestamp")
check("Level column correct",               row_cols[1] == "ERROR")
check("Message column correct",             row_cols[7] == "Database connection lost")
check("Extra column is JSON string",        '"host"' in row_cols[8])
check("Exception column empty for non-exc", row_cols[9] == "")
check("Exception column filled for exc",
      "ConnectionError" in next(csv.reader([csv_fmt.format(exc_record)]))[9])

# ── Markdown formatter ────────────────────────────────────────────────────────
print("\n── Markdown formatter ──")
md_basic = markdown.format(basic)
md_rich  = markdown.format(rich_record)
md_exc   = markdown.format(exc_record)

check("Has level heading",              "## " in md_basic)
check("Has INFO emoji",                 "ℹ" in md_basic)
check("Has ERROR emoji",                "❌" in md_rich)
check("Has CRITICAL emoji",             "🚨" in md_exc)
check("Has logger in meta",             "myapp" in md_basic)
check("Has message",                    "Server started" in md_basic)
check("Has extra collapsible",          "<details>" in md_rich)
check("Has JSON code block in extra",   "```json" in md_rich)
check("Has exception collapsible",      "<details>" in md_exc)
check("Has divider",                    "---" in md_basic)
check("No divider with flag off",       "---" not in markdown.format(basic, divider=False))

# ── BaseSink ──────────────────────────────────────────────────────────────────
print("\n── BaseSink ──")

class DummySink(BaseSink):
    def __init__(self, min_level=0):
        super().__init__(min_level=min_level, name="dummy")
        self.received = []
    def emit(self, record):
        self.received.append(record)

sink = DummySink(min_level=30)
check("should_handle ERROR(40) with min=30",   sink.should_handle(rich_record))
check("should_handle blocks INFO(20) with min=30", not sink.should_handle(basic))
sink.disable()
check("disabled sink blocks all records",      not sink.should_handle(rich_record))
sink.enable()
check("re-enabled sink passes records again",  sink.should_handle(rich_record))

# ── TerminalSink ──────────────────────────────────────────────────────────────
print("\n── TerminalSink ──")
terminal = TerminalSink(min_level=0)
check("TerminalSink instantiates",     terminal is not None)
check("should_handle DEBUG",           terminal.should_handle(basic))

# Emit all levels to verify no crashes
all_records = []
for level_name, level_no in [
    ("DEBUG",10),("INFO",20),("AUDIT",25),("WEBHOOK",28),
    ("WARNING",30),("SECURITY",35),("ERROR",40),("DEPLOY",45),("CRITICAL",50)
]:
    r = build_record(
        level_name=level_name, level_no=level_no,
        message=f"Test {level_name} message",
        logger_name="flowlog.test", module="test.py",
        func_name="run", line_no=1,
    )
    all_records.append(r)

print("\n  [Live terminal output — all 9 levels:]")
for r in all_records:
    terminal.emit(r)

check("All 9 levels emitted without crash", True)

# ── FileSink — text ───────────────────────────────────────────────────────────
print("\n── FileSink (text) ──")
with tempfile.TemporaryDirectory() as tmpdir:
    path = Path(tmpdir) / "test.log"
    sink = FileSink(path, fmt="text", min_level=0)
    sink.emit(basic)
    sink.emit(rich_record)
    sink.close()

    content = path.read_text(encoding="utf-8")
    check("File exists",                    path.exists())
    check("Contains INFO message",          "Server started" in content)
    check("Contains ERROR message",         "Database connection lost" in content)
    check("Contains extra",                 "db.riff.internal" in content)

# ── FileSink — JSON ───────────────────────────────────────────────────────────
print("\n── FileSink (json) ──")
with tempfile.TemporaryDirectory() as tmpdir:
    path = Path(tmpdir) / "test.json"
    sink = FileSink(path, fmt="json", min_level=0)
    sink.emit(basic)
    sink.emit(rich_record)
    sink.close()

    lines = path.read_text().strip().splitlines()
    check("Two lines written",              len(lines) == 2)
    check("Each line is valid JSON",        all(json.loads(l) for l in lines))
    check("Second line has extra",          "extra" in json.loads(lines[1]))

# ── FileSink — CSV ────────────────────────────────────────────────────────────
print("\n── FileSink (csv) ──")
with tempfile.TemporaryDirectory() as tmpdir:
    path = Path(tmpdir) / "test.csv"
    sink = FileSink(path, fmt="csv", min_level=0)
    sink.emit(basic)
    sink.emit(rich_record)
    sink.close()

    with open(path) as f:
        rows = list(csv.reader(f))
    check("Header row present",             rows[0][0] == "timestamp")
    check("Two data rows written",          len(rows) == 3)  # header + 2
    check("ERROR row level correct",        rows[2][1] == "ERROR")

# ── FileSink — Markdown ───────────────────────────────────────────────────────
print("\n── FileSink (markdown) ──")
with tempfile.TemporaryDirectory() as tmpdir:
    path = Path(tmpdir) / "test.md"
    sink = FileSink(path, fmt="markdown", min_level=0)
    sink.emit(basic)
    sink.emit(rich_record)
    sink.close()

    content = path.read_text(encoding="utf-8")
    check("Has markdown headings",          "## " in content)
    check("Both messages present",          "Server started" in content and
                                            "Database connection lost" in content)

# ── FileSink — rotation ───────────────────────────────────────────────────────
print("\n── FileSink (rotation) ──")
with tempfile.TemporaryDirectory() as tmpdir:
    path = Path(tmpdir) / "rotate.log"
    # max_bytes=1 forces rotation on every write
    sink = FileSink(path, fmt="text", min_level=0, max_bytes=1, backup_count=3)
    sink.emit(basic)
    sink.emit(basic)
    sink.emit(basic)
    sink.close()

    backups = list(Path(tmpdir).glob("rotate.log.*"))
    check("Backup files created",          len(backups) > 0)
    check("Current log file exists",       path.exists())

# ── FileSink — invalid format ─────────────────────────────────────────────────
print("\n── FileSink (validation) ──")
try:
    FileSink("/tmp/x.log", fmt="xml")
    check("Raises ValueError for bad fmt", False)
except ValueError:
    check("Raises ValueError for bad fmt", True)

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'─' * 40}")
if errors == 0:
    print(f"  All tests passed. Phases 2 & 3 are solid.\n")
else:
    print(f"  {errors} test(s) failed.\n")
    sys.exit(1)
