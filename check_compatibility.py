"""Compare the original and current PLC app with identical offline inputs."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from benchmark import FIXTURE, synthetic_bin


def snapshot(app_dir):
    sys.path.insert(0, str(app_dir))
    import main
    from block_read import fields, read_batched
    from conversation import route, summary
    from diagnosis import addresses
    from logic import extract

    data = synthetic_bin(96)
    if hasattr(main, "parse_program"):
        rows, logic, labels = main.parse_program(data)
    else:
        rows, logic, labels = main.parse(data), extract(data), main.labels_for(data)
    published = json.loads(FIXTURE.read_text())["words"]
    example_labels = {"CIO0.00": "ÖRNEK POMPA", "CIO0.01": "ÖRNEK ALARM"}
    extra = ["0101890001000001"]
    targets = [row[0] for row in rows] + ["D4", "D4.00", "T0001", "P_ON", "CIO100.02", "CIO101.03"]
    output = {"bin_rows": rows, "logic": logic, "labels": labels}

    for mode in ("block", "single", "fallback", "missing", "all_invalid"):
        requests = []
        reads = []
        disabled = set()

        def bridge(commands):
            requests.append(commands)
            responses = {}
            for command in commands:
                area, start, count = fields(command)
                if mode == "missing" and area == "82":
                    continue
                if mode == "all_invalid" or (mode == "fallback" and area == "B0" and count > 1):
                    responses[command] = {"ok": False, "response": "01011002"}
                    continue
                values = [published.get(str(index), index * 7 % 65536) if area == "B0"
                          else index % 2 if area == "09" else index * 3
                          for index in range(start, start + count)]
                encoded = "".join(f"{value:02X}" if area == "09" else f"{value:04X}"
                                  for value in values)
                responses[command] = {"ok": True, "response": "01010000" + encoded}
            return {"plc": "OFFLINE", "responses": responses}

        with patch("main.session.read", side_effect=lambda _, commands, enabled:
                   read_batched(bridge, commands, disabled, enabled)):
            for _ in range(2 if mode == "fallback" else 1):
                try:
                    values, responses, stats = main.read_targets(
                        "offline", "OFFLINE", targets, extra, enabled=mode != "single")
                except (ValueError, RuntimeError) as error:
                    reads.append({"error": str(error)})
                    continue
                queries = ["CIO0.00 neden?", "CIO0.00 nerede kullanılıyor?", "hangi alarmlar var?"]
                answers = []
                for question in queries:
                    row = rows[0] if "alarmlar" in question else route(question, rows, labels=example_labels)
                    answers.append(summary(row, rows, logic, values, example_labels, question))
                reads.append({"values": list(values.items()), "responses": list(responses.items()),
                              "stats": stats, "answers": answers,
                              "dependencies": sorted(addresses(rows[0][0], rows, logic))})
        output[mode] = {"calls": requests, "reads": reads}
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--snapshot", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.snapshot:
        print(json.dumps(snapshot(args.snapshot.resolve()), ensure_ascii=True))
        return
    if not args.baseline:
        parser.error("--baseline is required")
    paths = [args.baseline, Path(__file__).resolve().parent]
    for seed in ("0", "17"):
        results = []
        for path in paths:
            run = subprocess.check_output(
                [sys.executable, str(Path(__file__).resolve()), "--snapshot", str(path.resolve())],
                env={**os.environ, "PYTHONHASHSEED": seed},
            )
            results.append(json.loads(run))
        for scenario, expected in results[0].items():
            if expected != results[1].get(scenario):
                raise SystemExit(f"Mismatch in {scenario} with hash seed {seed}")
    print("Matched BIN rows, logic, values, FINS requests, responses, errors and existing answers in all five scenarios.")


if __name__ == "__main__":
    main()
