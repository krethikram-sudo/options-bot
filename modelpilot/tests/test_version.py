"""Version hygiene: semver shape, and the CHANGELOG must document the
current version — so a bump can't ship without telling customers what
changed. Works in both the monorepo and the published beta layout."""

import re
from pathlib import Path

import modelpilot


def _changelog() -> str:
    package_dir = Path(modelpilot.__file__).parent
    for candidate in (package_dir / "packaging" / "CHANGELOG.md",   # monorepo
                      package_dir.parent / "CHANGELOG.md"):          # published repo
        if candidate.exists():
            return candidate.read_text()
    raise AssertionError("CHANGELOG.md not found in either layout")


def test_version_is_semver():
    assert re.fullmatch(r"\d+\.\d+(\.\d+)?", modelpilot.__version__)


def test_changelog_documents_current_version():
    assert f"## {modelpilot.__version__}" in _changelog(), (
        f"CHANGELOG has no entry for {modelpilot.__version__} — every version "
        f"bump needs a changelog entry (integer = breaking, decimal = features/fixes)")
