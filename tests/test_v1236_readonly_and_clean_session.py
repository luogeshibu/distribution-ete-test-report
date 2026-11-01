from pathlib import Path

import pytest

from distribution_signal_verifier.distribution_signal_verifier import (
    InputError,
    assert_oracle_read_only_sql,
    build_distribution_point_sql,
    build_distribution_protocol_sql,
    build_rmu_search_sql,
    build_rmu_id_sql,
    build_rmu_sql,
    build_smart_inventory_sql,
)


def test_all_builtin_oracle_queries_are_accepted_as_read_only():
    queries = [
        build_rmu_sql(['RMU-A'])[0],
        build_rmu_search_sql('346', 50)[0],
        build_rmu_id_sql([1001, 1002])[0],
        build_distribution_point_sql([1001, 1002])[0],
        build_distribution_protocol_sql([1001, 1002])[0],
        build_smart_inventory_sql('SS', 'FEEDER', 'AREA')[0],
    ]
    for sql in queries:
        assert_oracle_read_only_sql(sql)


@pytest.mark.parametrize(
    'sql',
    [
        'UPDATE d5000.t SET x=1',
        'INSERT INTO d5000.t(x) VALUES (1)',
        'DELETE FROM d5000.t',
        'MERGE INTO d5000.t USING d5000.s ON (1=1) WHEN MATCHED THEN UPDATE SET x=1',
        'CREATE TABLE t(x NUMBER)',
        'ALTER TABLE t ADD y NUMBER',
        'DROP TABLE t',
        'TRUNCATE TABLE t',
        'BEGIN NULL; END;',
        'CALL some_proc()',
        'COMMIT',
        'SELECT * FROM d5000.t FOR UPDATE',
        'SELECT * FROM d5000.t; DELETE FROM d5000.t',
        'WITH x AS (SELECT 1 n FROM dual) SELECT * FROM x FOR UPDATE',
    ],
)
def test_oracle_write_or_locking_sql_is_rejected(sql):
    with pytest.raises(InputError):
        assert_oracle_read_only_sql(sql)


def test_read_only_guard_ignores_words_inside_literals_and_comments():
    assert_oracle_read_only_sql("SELECT 'UPDATE DELETE' AS txt FROM dual -- DROP TABLE x")
    assert_oracle_read_only_sql("/* INSERT INTO x */ WITH q AS (SELECT 1 n FROM dual) SELECT n FROM q")


def test_browser_does_not_persist_or_auto_restore_test_results_on_normal_open():
    report = Path('web/distribution_report.html').read_text(encoding='utf-8')
    assert 'localStorage.setItem(STORAGE_KEY, JSON.stringify(exportState()))' not in report
    assert 'localStorage.getItem(STORAGE_KEY)' not in report
    assert 'DistributionLanguageController' in report
    assert 'localStorage.setItem(key, current)' in report
    assert 'localStorage.removeItem(STORAGE_KEY)' in report
    assert 'if (!RESUME_REPORT_UUID) return false;' in report
    # v1.2.41 allows only a one-time same-tab handoff while adding/removing an RMU.
    assert 'const RMU_HANDOFF_PREFIX = "distribution_rmu_nav_handoff:";' in report
    assert 'sessionStorage.setItem(key, JSON.stringify(payload));' in report
    assert 'sessionStorage.removeItem(key);' in report
    assert 'url.searchParams.delete("handoff");' in report
    assert 'const restoredByRmuHandoff = restoreRmuNavigationHandoff();' in report
    assert 'if (!restoredByRmuHandoff) await restoreServerDraft();' in report


def test_home_and_reset_current_test_actions_are_present():
    report = Path('web/distribution_report.html').read_text(encoding='utf-8')
    assert 'id="btn-home"' in report
    assert 'id="btn-reset-current"' in report
    assert 'function resetCurrentTest()' in report
    assert 'freshClientState();' in report
    assert 'rememberReportUuid("", false);' in report
    assert "window.location.assign('/?network=distribution');" in report


def test_live_oracle_execution_paths_call_read_only_guard():
    server = Path('src/distribution_signal_verifier/live_report_server.py').read_text(encoding='utf-8')
    core = Path('src/distribution_signal_verifier/distribution_signal_verifier.py').read_text(encoding='utf-8')
    assert server.count('assert_oracle_read_only_sql(sql)') >= 2
    assert 'assert_oracle_read_only_sql(sql)' in core
    assert 'def build_rmu_id_sql' in core
    assert 'oracle_access=STRICT_READ_ONLY' in server
