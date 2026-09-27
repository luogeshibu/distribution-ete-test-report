import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_canonical_config_defaults():
    cfg=json.loads((ROOT/'config/report_config.json').read_text(encoding='utf-8'))
    assert cfg['server']['port']==8899
    assert 'print_password' in cfg['security']
    assert set(cfg['oracle']) >= {'host','port','service','dsn','user','password'}

def test_example_matches_runtime_config_shape_without_requiring_secrets():
    actual=json.loads((ROOT/'config/report_config.json').read_text(encoding='utf-8'))
    example=json.loads((ROOT/'config/report_config.example.json').read_text(encoding='utf-8'))
    assert set(example)==set(actual)=={'server','oracle','security'}
    assert set(example['server'])==set(actual['server'])
    assert set(example['oracle'])==set(actual['oracle'])
    assert set(example['security'])==set(actual['security'])
    # The checked-in example may be sanitized; the local canonical runtime
    # config is allowed to retain the operator's working Oracle settings.

def test_build_uses_canonical_config():
    text=(ROOT/'scripts/build_release.ps1').read_text(encoding='utf-8')
    assert 'config\\report_config.json' in text
    assert 'print_password = ""' not in text
    assert 'port = 8787' not in text

def test_runtime_has_no_legacy_oracle_module_fallback():
    text=(ROOT/'src/distribution_signal_verifier/live_report_server.py').read_text(encoding='utf-8')
    assert 'oracle_private_config.py' not in text
    assert 'configured_print_password = "NARI"' in text
