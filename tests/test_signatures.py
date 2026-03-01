from src.signatures import SignatureExtractor
from src.core import SATGenerator

def test_signature_extraction_demo():
    gen = SATGenerator()
    inst = gen.random_kcnf(20, 80, 3, seed=99)
    
    extractor = SignatureExtractor({"signature_mode": {"mode": "demo"}})
    feats, mode = extractor.extract_all(inst)
    
    assert mode == "DEMO"
    assert "spectral_gap_proxy" in feats
    assert "thermo_beta_critical_proxy" in feats
    assert "algebra_mean_clause_len" in feats
    assert "algebra_horn_fraction" in feats
