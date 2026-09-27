from pathlib import Path

from distribution_signal_verifier.distribution_signal_verifier import RmuMapping, build_payload


def test_distribution_payload_serializes_large_combined_id_as_text():
    huge_id = 12345678901234567890
    mapping = [
        RmuMapping(
            combined_id=huge_id,
            rmu_name='22004',
            adms_gss_fid='JED-CTL-EEH-AH333-22004',
        )
    ]
    payload = build_payload(
        mapping,
        [{
            'POINT_TYPE': 'Status Indication',
            'COMBINED_ID': huge_id,
            'RMU_NAME': '22004',
            'DOT_NO': 1003,
            'SIGNAL_NAME': '22004 KQ1 state',
        }],
        protocol='IEC-104',
    )
    assert payload['distribution_mappings'][0]['combined_id'] == str(huge_id)
    assert payload['points'][0]['combined_id'] == str(huge_id)
    assert payload['points'][0]['rmu_display_name'] == 'JED-CTL-EEH-AH333-22004'


def test_multi_device_browser_grouping_prefers_full_fid_over_combined_id():
    html = (Path(__file__).resolve().parents[1] / 'web' / 'distribution_report.html').read_text(encoding='utf-8')
    rmu_start = html.index('function rmuIdentity(m)')
    point_start = html.index('function pointRmuIdentity(p)')
    rmu_block = html[rmu_start:point_start]
    point_block = html[point_start:html.index('function rmuGroups()', point_start)]
    assert rmu_block.index("return 'fid:' + String(m.adms_gss_fid).trim();") < rmu_block.index("return 'id:' + String(m.combined_id).trim();")
    assert point_block.index("return 'fid:' + String(p.rmu_display_name).trim();") < point_block.index("return 'id:' + String(p.combined_id).trim();")


def test_add_remove_handoff_has_stable_per_device_point_key_fallback():
    html = (Path(__file__).resolve().parents[1] / 'web' / 'distribution_report.html').read_text(encoding='utf-8')
    assert 'function pointStateKey(p)' in html
    assert 'pointRmuIdentity(p),' in html
    assert 'point_keys: pointKeys,' in html
    assert '(data.point_keys && data.point_keys[pointStateKey(p)])' in html
