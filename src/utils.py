import hashlib
import random
from datetime import datetime, timezone

def _u32_from_sha256(s: str) -> int:
    h = hashlib.sha256(s.encode("utf-8")).hexdigest()
    return int(h[:8], 16)  # 32-bit

def rng_for_instance(instance_id: str, salt: str = "") -> random.Random:
    seed = _u32_from_sha256(instance_id + "|" + salt)
    return random.Random(seed)

def now_z() -> str:
    return datetime.now(timezone.utc).isoformat() + "Z"
