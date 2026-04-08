"""
Campaign Memory Persistence (ReMe File-Based Pattern).
Tracks explored parameter regions across campaigns to enable incremental exploration.
"""
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Set, Tuple


class CampaignMemory:
    """
    Persistent memory for NP-ATLAS campaigns.
    Uses Markdown files for human-readable memory (inspired by ReMe CoPaw pattern).
    """
    def __init__(self, working_dir: str = "."):
        self.working_dir = Path(working_dir)
        self.memory_file = self.working_dir / "MEMORY.md"
        self.memory_dir = self.working_dir / "memory"
        self.memory_dir.mkdir(exist_ok=True)

    def load_explored_points(self) -> Set[str]:
        """Load set of already-explored parameter point keys from MEMORY.md."""
        explored = set()
        if not self.memory_file.exists():
            return explored

        content = self.memory_file.read_text(encoding="utf-8")
        in_explored = False
        for line in content.splitlines():
            if line.strip().startswith("## Explored Points"):
                in_explored = True
                continue
            if in_explored and line.startswith("## "):
                break
            if in_explored and line.startswith("- `"):
                key = line.strip().lstrip("- `").rstrip("`").split("`")[0]
                explored.add(key)
        return explored

    def point_key(self, n: int, ratio: float, seed: int, generator: str) -> str:
        return f"n={n}|r={ratio:.3f}|s={seed}|g={generator}"

    def save_campaign_summary(self, campaign_id: str, v: Dict[str, Any],
                               gates: Dict[str, Any], n_instances: int,
                               explored_keys: Set[str]) -> None:
        """Append campaign to daily log and update MEMORY.md."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        daily_log = self.memory_dir / f"{today}.md"

        # Append to daily log
        entry = f"\n### Campaign: {campaign_id}\n"
        entry += f"- **Timestamp**: {datetime.now(timezone.utc).isoformat()}Z\n"
        entry += f"- **Instances**: {n_instances}\n"
        entry += f"- **Verdict**: {gates.get('final_verdict', 'UNKNOWN')}\n"
        entry += f"- **Vector dims**: {len(v.get('coordinates', []))}\n"
        entry += f"- **Coordinates**: `{v.get('coordinates', [])}`\n"
        passed = sum(1 for k, x in gates.items() if isinstance(x, dict) and x.get("status") == "PASS")
        total = sum(1 for k, x in gates.items() if isinstance(x, dict))
        entry += f"- **Gates**: {passed}/{total} passed\n"

        with open(daily_log, "a", encoding="utf-8") as f:
            if daily_log.stat().st_size == 0:
                f.write(f"# NP-ATLAS Memory Log — {today}\n")
            f.write(entry)

        # Update MEMORY.md
        self._update_memory_file(campaign_id, v, gates, explored_keys)

    def _update_memory_file(self, campaign_id: str, v: Dict[str, Any],
                             gates: Dict[str, Any], explored_keys: Set[str]) -> None:
        """Rewrite MEMORY.md with accumulated knowledge."""
        lines = []
        lines.append("# NP-ATLAS Campaign Memory\n\n")
        lines.append(f"> Last updated: {datetime.now(timezone.utc).isoformat()}Z\n\n")

        # Best vector so far
        lines.append("## Best Vector\n\n")
        lines.append(f"- **Campaign**: {campaign_id}\n")
        lines.append(f"- **Verdict**: {gates.get('final_verdict', 'UNKNOWN')}\n")
        lines.append(f"- **Coordinates**: `{v.get('coordinates', [])}`\n")
        lines.append(f"- **Stability**: {v.get('stability_score', 'N/A')}\n\n")

        # Gate results
        lines.append("## Gate Results\n\n")
        lines.append("| Gate | Status | Score |\n")
        lines.append("|---|---|---|\n")
        for k, res in gates.items():
            if isinstance(res, dict) and "status" in res:
                lines.append(f"| {k} | {res['status']} | {res.get('score', 'N/A')} |\n")
        lines.append("\n")

        # Explored points
        lines.append("## Explored Points\n\n")
        for key in sorted(explored_keys):
            lines.append(f"- `{key}`\n")

        with open(self.memory_file, "w", encoding="utf-8") as f:
            f.writelines(lines)
