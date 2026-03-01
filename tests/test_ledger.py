import tempfile
from pathlib import Path
from src.ledger import Ledger

def test_ledger_chain_validity():
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
        path = f.name
        
    try:
        ledger = Ledger(path=path)
        
        h1 = ledger.record("TEST_EVENT", {"foo": "bar"})
        h2 = ledger.record("TEST_EVENT_2", {"x": 1})
        
        assert ledger.count_events() == 2
        
        valid, msg = ledger.validate_chain()
        assert valid is True
        
        # Test tampering
        import json
        with open(path, "r") as r:
            lines = r.readlines()
        
        bad_line = lines[1].replace('"x": 1', '"x": 2')
        with open(path, "w") as w:
            w.write(lines[0])
            w.write(bad_line)
            
        valid2, msg2 = Ledger(path=path).validate_chain()
        assert valid2 is False
        assert "Hash mismatch" in msg2
        
    finally:
        import os
        if os.path.exists(path):
            os.remove(path)
