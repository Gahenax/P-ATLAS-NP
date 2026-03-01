import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Tuple, List
from src.utils import now_z

class Ledger:
    def __init__(self, path: str = "ledger.jsonl"):
        self.path = Path(path)
        self.prev_hash = "0" * 64
        if self.path.exists():
            self._load_tail()

    def _load_tail(self) -> None:
        with open(self.path, "r", encoding="utf-8") as f:
            last_line = None
            for last_line in f:
                pass
            if last_line:
                last = json.loads(last_line)
                self.prev_hash = last.get("self_hash", "0" * 64)

    def record(self, event_type: str, data: Dict[str, Any]) -> str:
        event = {
            "event_type": event_type,
            "ts": now_z(),
            "prev_hash": self.prev_hash,
            **data
        }
        # hash excluyendo self_hash
        event_for_hash = {k: v for k, v in event.items() if k != "self_hash"}
        event_str = json.dumps(event_for_hash, sort_keys=True, default=str)
        self_hash = hashlib.sha256(event_str.encode("utf-8")).hexdigest()
        event["self_hash"] = self_hash

        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

        self.prev_hash = self_hash
        return self_hash

    def count_events(self) -> int:
        if not self.path.exists():
            return 0
        with open(self.path, "r", encoding="utf-8") as f:
            return sum(1 for _ in f)

    def validate_chain(self) -> Tuple[bool, str]:
        if not self.path.exists():
            return True, "No ledger to validate"

        prev_hash = "0" * 64
        errors: List[str] = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as e:
                    return False, f"Line {line_num}: Invalid JSON ({e})"

                if event.get("prev_hash") != prev_hash:
                    errors.append(f"Line {line_num}: Hash-chain break")

                test_event = {k: v for k, v in event.items() if k != "self_hash"}
                test_str = json.dumps(test_event, sort_keys=True, default=str)
                computed = hashlib.sha256(test_str.encode("utf-8")).hexdigest()
                if computed != event.get("self_hash"):
                    errors.append(f"Line {line_num}: Hash mismatch (tampering)")

                prev_hash = event.get("self_hash", "0" * 64)

        if errors:
            return False, "; ".join(errors[:3])
        return True, f"Chain valid, {self.count_events()} events"
