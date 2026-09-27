from pathlib import Path

from distribution_signal_verifier.live_report_server import LiveDataProvider

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "web" / "distribution_report.html"
HISTORY = ROOT / "web" / "history.html"
DASHBOARD = ROOT / "web" / "dashboard.html"
SERVER = ROOT / "src" / "distribution_signal_verifier" / "live_report_server.py"
QUERY = ROOT / "src" / "distribution_signal_verifier" / "distribution_signal_verifier.py"


def test_main_report_english_dictionary_has_no_chinese_result_or_kind_labels():
    text = REPORT.read_text(encoding="utf-8")
    assert 'verdictConditional: "Pass with comments"' in text
    assert 'kindYX: "Status Indication"' in text
    assert 'kindYC: "Analog Measurement"' in text
    assert 'kindYK: "Single/Double Command"' in text
    assert 'kindPD: "Step Command"' in text
    assert 'kindSP: "Setpoint Command"' in text


def test_main_report_chinese_dictionary_has_chinese_operation_labels():
    text = REPORT.read_text(encoding="utf-8")
    assert 'printTitle: "端到端测试报告（ADMS）"' in text
    assert 'btnPrintDraft: "打印 / 草稿"' in text
    assert 'btnSelTab: "全选当前页签"' in text
    assert 'btnClearTab: "清空当前页签勾选"' in text
    assert 'toastBulkEmpty: "当前页签没有测点"' in text
    assert 'resultConditional: "通过（带备注）"' in text


def test_language_is_single_source_of_truth_across_live_device_operations():
    report = REPORT.read_text(encoding="utf-8")
    server = SERVER.read_text(encoding="utf-8")
    assert "window.getReportLanguage = () => lang;" in report
    assert 'new CustomEvent("report-language-change", {detail: {lang}})' in report
    assert "window.applyLiveLanguage = applyLiveLanguage;" in server
    assert "window.addEventListener('report-language-change', applyLiveLanguage);" in server
    assert "liveText('未查询到匹配的设备', 'No matching device found')" in server
    assert "liveText('设备搜索失败，请查看服务端日志。', 'Device search failed. Please check the server log.')" in server


def test_language_preference_and_global_controller_exist_on_all_three_pages():
    for path in (REPORT, HISTORY, DASHBOARD):
        text = path.read_text(encoding="utf-8")
        assert "localStorage" in text
        assert "DistributionLanguageController" in text
        assert "LANGUAGE_CONTROLLER" in text
        assert "sessionStorage.getItem(LANG_KEY" not in text

def test_dashboard_export_is_generated_in_active_language():
    dashboard = DASHBOARD.read_text(encoding="utf-8")
    server = SERVER.read_text(encoding="utf-8")
    assert "JSON.stringify({filters:lastFilters,lang})" in dashboard
    assert 'def _summary_report_html(summary: Mapping[str, Any], lang: str = "zh")' in server
    assert "self.provider.export_dashboard_summary(filters, lang=lang)" in server

    summary = {
        "scope": {"subcontrolarea": "JED", "substation": "EEH", "feeder": "AH333", "date_from": "", "date_to": ""},
        "coverage_available": False,
        "generated_at": "2026-09-27T12:00:00+03:00",
        "totals": {"total": 1, "tested": 1, "in_progress": 0, "untested": None, "passed": 0, "conditional": 1, "failed": 0, "completion_rate": None, "pass_rate": 100.0},
        "feeders": [],
        "devices": [{
            "subcontrolarea_name": "JED",
            "substation_name": "EEH",
            "feeder_name": "AH333",
            "display_name": "JED-CTL-EEH-AH333-22004",
            "rmu_type": "2L1T",
            "status": "tested",
            "verdict": "conditional",
            "tested_at": "2026-09-27",
            "lead": "Tony",
        }],
    }
    en_html = LiveDataProvider._summary_report_html(summary, lang="en")
    assert "Distribution ETE Overall Test Report" in en_html
    assert "Statistics by Feeder" in en_html
    assert "Device Details" in en_html
    assert "Pass with comments" in en_html
    assert "已调试" not in en_html
    assert "通过（带备注）" not in en_html

    zh_html = LiveDataProvider._summary_report_html(summary, lang="zh")
    assert "配网 ETE 总体测试报告" in zh_html
    assert "按馈线统计" in zh_html
    assert "设备明细" in zh_html
    assert "通过（带备注）" in zh_html
    assert "Statistics by Feeder" not in zh_html
    assert "Pass with comments" not in zh_html


def test_dashboard_does_not_surface_raw_wrong_language_server_warning():
    text = DASHBOARD.read_text(encoding="utf-8")
    assert "return raw?t('cacheWarning'):''" in text
    assert "Oracle device-inventory query failed; the latest cache is being used." in text
    assert "Oracle 设备台账查询失败，已使用最近缓存。" in text


def test_oracle_query_path_remains_read_only_and_existing_search_functions_remain():
    text = QUERY.read_text(encoding="utf-8")
    server = SERVER.read_text(encoding="utf-8")
    assert "def build_rmu_search_sql(" in text
    assert "def build_rmu_id_sql(" in text
    assert "def query_rmu_mapping(" in text
    assert "assert_oracle_read_only_sql(sql)" in text
    assert "assert_oracle_read_only_sql(sql)" in server
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == "1.2.62"
