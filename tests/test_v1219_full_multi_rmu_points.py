from pathlib import Path


def _html():
    return (Path(__file__).resolve().parents[1] / "web" / "distribution_report.html").read_text(encoding="utf-8")


def test_multi_rmu_points_use_independent_full_height_blocks():
    html = _html()
    assert 'id="multi-rmu-points-root"' in html
    assert 'id="single-rmu-points-wrap"' in html
    assert '.rmu-point-group .table-wrap {' in html
    assert 'max-height: none;' in html
    assert 'overflow-y: visible;' in html
    assert 'function renderMultiRmuPointTables(rows, groups, printing)' in html
    assert 'root.classList.add("active")' in html
    assert 'singleWrap.style.display = "none"' in html


def test_each_rmu_gets_its_own_4x_heading_and_table():
    html = _html()
    assert 'title.textContent = "4." + group.index + " " + group.label' in html
    assert 'const groupRows = rows.filter((p) => pointRmuIdentity(p) === group.key);' in html
    assert 'table.className = "points";' in html
    assert 'groupRows.forEach((p) =>' in html


def test_single_rmu_keeps_legacy_table_path():
    html = _html()
    assert 'if (groups.length > 1) {' in html
    assert 'singleWrap.style.display = "";' in html
    assert 'appendPointRow(tbody, p, printing);' in html
