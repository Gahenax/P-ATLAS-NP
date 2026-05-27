import json
import tempfile
import os
import hashlib
from pathlib import Path
from src.ledger import Ledger

def test_validate_chain_invalid_json():
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
        path = f.name
        # Line 1: Invalid JSON
        f.write('{ invalid_json }\n')
        # Line 2: Valid JSON so _load_tail doesn't crash
        f.write('{"event_type": "START", "ts": "2023-01-01T00:00:00Z", "prev_hash": "0000000000000000000000000000000000000000000000000000000000000000", "self_hash": "somehash"}\n')

    try:
        ledger = Ledger(path=path)
        valid, msg = ledger.validate_chain()
        assert valid is False
        assert "Line 1: Invalid JSON" in msg
    finally:
        if os.path.exists(path):
            os.remove(path)

def test_validate_chain_hash_chain_break():
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
        path = f.name

    try:
        ledger = Ledger(path=path)
        h1 = ledger.record("EVENT1", {"data": 1})
        h2 = ledger.record("EVENT2", {"data": 2})

        with open(path, "r") as f:
            lines = f.readlines()

        # Manually break the chain in the second event
        event2 = json.loads(lines[1])
        event2["prev_hash"] = "wrong_hash"

        # We need to re-hash it to avoid "Hash mismatch" error and specifically trigger "Hash-chain break"
        test_event2 = {k: v for k, v in event2.items() if k != "self_hash"}
        test_str2 = json.dumps(test_event2, sort_keys=True, default=str)
        event2["self_hash"] = hashlib.sha256(test_str2.encode("utf-8")).hexdigest()

        lines[1] = json.dumps(event2) + "\n"

        with open(path, "w") as f:
            f.writelines(lines)

        valid, msg = Ledger(path=path).validate_chain()
        assert valid is False
        assert "Line 2: Hash-chain break" in msg

    finally:
        if os.path.exists(path):
            os.remove(path)
