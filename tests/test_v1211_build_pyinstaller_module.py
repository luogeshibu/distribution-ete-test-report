from pathlib import Path


def test_build_uses_python_module_not_pyinstaller_exe():
    root = Path(__file__).resolve().parents[1]
    text = (root / "scripts" / "build_release.ps1").read_text(encoding="utf-8")
    assert "& $python -m PyInstaller --noconfirm" in text
    assert 'Scripts\\pyinstaller.exe' not in text
    assert "& $pyinstaller" not in text


def test_build_does_not_unconditionally_reinstall_pyinstaller():
    root = Path(__file__).resolve().parents[1]
    text = (root / "scripts" / "build_release.ps1").read_text(encoding="utf-8")
    assert "importlib.util.find_spec('PyInstaller')" in text
    assert '& $python -c "import PyInstaller"' not in text
    assert "if ($pyInstallerAvailable -ne \"1\")" in text
