from pathlib import Path


def test_site_point_sql_is_not_rewritten_and_rows_are_tagged_per_mapping():
    text = (Path(__file__).parents[1] / "src" / "distribution_signal_verifier" / "live_report_server.py").read_text(encoding="utf-8")
    assert 'self.config.distribution_point_sql, "combined_id", [combined_id]' in text
    assert 'tagged["COMBINED_ID"] = combined_id' in text
    assert 'for item in mappings:' in text
