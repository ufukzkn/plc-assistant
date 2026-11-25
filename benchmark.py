"""Repeatable offline measurements against an extracted baseline or this directory."""
import argparse
import json
import math
import platform
import statistics
import struct
import sys
from pathlib import Path
from time import perf_counter_ns, sleep
from unittest.mock import patch

FIXTURE = Path(__file__).with_name("fixtures") / "omron_p029_read.json"


def synthetic_bin(count):
    # Minimal binary matching the experimental decoder's expected layout.
    header = bytes(0x8C0) + bytes.fromhex("6144010024000000")
    return header + b"".join(
        struct.pack(">HHHHHH", 0xE204, index, 0xFA04, index, 0x2400, 0)
        for index in range(count)
    )


def sample(work, runs, warmups=5):
    for _ in range(warmups):
        work()
    times = []
    for _ in range(runs):
        start = perf_counter_ns()
        work()
        times.append((perf_counter_ns() - start) / 1_000_000)
    return {
        "n": runs,
        "p50_ms": round(statistics.median(times), 5),
        "p95_ms": round(sorted(times)[math.ceil(runs * .95) - 1], 5),
        "samples_ms": [round(value, 5) for value in times],
    }


def benchmark(app_dir):
    sys.path.insert(0, str(app_dir.resolve()))
    import main
    from block_read import fields, read_batched
    from cikis import decode
    from logic import extract

    fixture = json.loads(FIXTURE.read_text())
    published = {int(key): value for key, value in fixture["words"].items()}
    delay = 0
    calls = []
    disabled = set()
    reject_blocks = False

    def transport(commands):
        responses = {}
        calls.extend(commands)
        for cmd in commands:
            area, start, count = fields(cmd)
            if delay:
                sleep(delay)
            if reject_blocks and area == "B0" and count > 1:
                responses[cmd] = {"ok": False, "response": "01011002"}
                continue
            words = [published.get(i, i * 313 % 65536) if area == "B0"
                     else (i % 2 if area == "09" else i * 313 % 65536)
                     for i in range(start, start + count)]
            payload = "".join(f"{word:02X}" if area == "09" else f"{word:04X}"
                              for word in words)
            responses[cmd] = {"ok": True, "response": "01010000" + payload}
        return {"plc": "OFFLINE", "responses": responses}

    assert transport([fixture["command"]])["responses"][fixture["command"]]["response"] == fixture["response"]

    def bridge(cdm, commands, enabled):
        calls.clear()
        return read_batched(transport, commands, disabled, enabled)

    cases = {}
    targets = {f"CIO{i}.{bit:02d}" for i in range(100, 124) for bit in range(8)}
    targets |= {f"D{i}" for i in range(20)} | {f"T{i:04d}" for i in range(5)}
    with patch("main.session.read", side_effect=bridge):
        def read(enabled=True):
            return main.read_targets("offline", "OFFLINE", targets, ["0101890001000001"], enabled)
        values, responses, stats = read()
        assert values["CIO100.02"] == 1 and values["CIO101.03"] == 1
        assert (values, responses) == read(False)[:2]
        cases["poll_cpu"] = {**sample(read, 251), **stats, "targets": len(targets)}
        small_targets = {f"CIO{i}.{bit:02d}" for i in range(100, 116) for bit in range(3)}
        small_targets |= {f"D{i}" for i in range(6)} | {f"T{i:04d}" for i in range(3)}

        def read_small():
            return main.read_targets("offline", "OFFLINE", small_targets)

        _, _, small_stats = read_small()
        cases["poll_cpu_57_targets"] = {**sample(read_small, 251), **small_stats, "targets": len(small_targets)}
        delay = .001
        cases["poll_simulated_1ms_per_command"] = {**sample(read, 61), **stats}
        delay = 0
        reject_blocks = True

        def retry_once():
            disabled.clear()
            return read()

        _, _, retry_stats = retry_once()
        assert retry_stats["fallback"] == 24 and retry_stats["disabled"] == ["B0"]
        assert read()[0] == values
        cases["poll_rejected_blocks"] = {**sample(retry_once, 151), **retry_stats}

    data = synthetic_bin(4096)
    rows = decode(data)
    logic = extract(data)
    assert len(rows) == len(logic) == 4096 and logic[rows[0][2]] == [("LD", "CIO0.00")]

    def load():
        if hasattr(main, "parse_program"):
            return main.parse_program(data)
        return decode(data), extract(data), main.labels_for(data)

    cases["offline_program_4096_targets"] = sample(load, 101)
    return {"python": platform.python_version(), "platform": platform.platform(), "cases": cases}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-dir", type=Path, default=Path(__file__).parent)
    options = parser.parse_args()
    print(json.dumps(benchmark(options.app_dir), indent=2))
