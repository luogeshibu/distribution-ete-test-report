from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_static_template_uses_equipment_report_title():
    text = (ROOT / 'web' / 'distribution_report.html').read_text(encoding='utf-8')
    assert 'Distribution Equipment Signal End-to-End Test Report · ADMS' in text
    assert 'Distribution RMU RTU Signal End-to-End Test Report · ADMS' not in text

def test_runtime_injection_uses_equipment_report_title():
    text = (ROOT / 'src' / 'distribution_signal_verifier' / 'live_report_server.py').read_text(encoding='utf-8')
    assert "I18N.en.hdrTitle = 'Distribution Equipment Signal End-to-End Test Report · ADMS'" in text
    assert 'Distribution Equipment · Substation' in text

def test_generated_report_source_uses_equipment_title():
    text = (ROOT / 'src' / 'distribution_signal_verifier' / 'distribution_signal_verifier.py').read_text(encoding='utf-8')
    assert 'Distribution Equipment Signal End-to-End Test Report · ADMS' in text
    assert 'Distribution RMU RTU Signal End-to-End Test Report · ADMS' not in text