import json
import unittest
from unittest.mock import patch

from benchmark import FIXTURE, synthetic_bin
from block_read import batches, fields, read_batched
from main import parse_program, read_targets


class Pipeline(unittest.TestCase):
    def test_omron_words_replay_through_read_targets(self):
        example = json.loads(FIXTURE.read_text())
        captured = example["command"]
        calls = []

        def send(commands):
            self.assertEqual(commands, [captured])
            calls.append(commands)
            return {
                "plc": "OFFLINE",
                "responses": {captured: {"ok": True, "response": example["response"]}},
            }

        with patch("main.session.read", side_effect=lambda _, commands, enabled:
                   read_batched(send, commands, set(), enabled)):
            values, responses, stats = read_targets(
                "offline", "OFFLINE", ["CIO100.02", "CIO100.01", "CIO101.03", "CIO101.00"])
        self.assertEqual(values, {"CIO100.02": 1, "CIO100.01": 0, "CIO101.03": 1, "CIO101.00": 0})
        self.assertEqual({response["response"] for response in responses.values()},
                         {"010100001234", "010100005678"})
        self.assertEqual((stats["commands"], stats["single"], len(calls)), (1, 2, 1))

    def test_same_plan_reads_fresh_values_and_handles_partial_failures(self):
        targets = {"D20", "D20.00", "CIO100.01", "CIO100.02", "T0001", "P_ON"}
        words = iter(("0001", "0002"))

        def send(commands):
            next_word = next(words)
            responses = {}
            for command in commands:
                area, _, _ = fields(command)
                raw = {"82": next_word, "09": "01", "B0": "broken"}[area]
                responses[command] = {"ok": True, "response": "01010000" + raw}
            return {"plc": "OFFLINE", "responses": responses}

        with patch("main.session.read", side_effect=lambda _, commands, enabled:
                   read_batched(send, commands, set(), enabled)):
            first, _, _ = read_targets("offline", "OFFLINE", targets)
            second, _, _ = read_targets("offline", "OFFLINE", targets)
        self.assertEqual(first, {"D20": 1, "D20.00": 1, "T0001": 1,
                                 "CIO100.01": None, "CIO100.02": None})
        self.assertEqual((second["D20"], second["D20.00"]), (2, 0))

    def test_cached_plan_is_not_mutable_through_public_api(self):
        commands = ("0101B00064000001", "0101B00065000001")
        plan = batches(commands)
        next(iter(plan.values())).clear()
        self.assertEqual(batches(commands), {"0101B00064000002": list(commands)})
        self.assertEqual(len(batches(commands, {"B0"})), 2)

    def test_offline_bin_and_truncated_tail(self):
        data = synthetic_bin(2)
        rows, logic, labels = parse_program(data)
        self.assertEqual(rows, [
            ("CIO0.00", "OUT", "08CC", "FA04 0000"),
            ("CIO0.01", "OUT", "08D8", "FA04 0001"),
        ])
        self.assertEqual(logic, {"08CC": [("LD", "CIO0.00")], "08D8": [("LD", "CIO0.01")]})
        self.assertEqual(labels, {})
        self.assertEqual(parse_program(data + b"\xFA\x04"), (rows, logic, labels))
        with self.assertRaises(ValueError):
            parse_program(bytes(3000))
