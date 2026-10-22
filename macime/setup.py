"""Run from the repository root: python macime/setup.py py2app.

This bundles Python and PyObjC, so the installed input source needs no venv.
Build separately on Apple Silicon and Intel; no cross-compilation is implied.
"""

import sys
from pathlib import Path

if sys.platform != "darwin":
    raise SystemExit("KorKanaIME.app must be built on macOS.")

from setuptools import setup

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

packages = ["korkana", "macime"]
try:
    import mozcpy
except ImportError:
    pass  # A kana-only build is supported.
else:
    # Including a package includes its dictionary data via py2app.
    packages.append("mozcpy")

setup(
    name="KorKanaIME",
    version="0.1.0",
    app=[{"script": str(root / "macime" / "app.py"), "dest_base": "KorKanaIME"}],
    options={"py2app": {
        "argv_emulation": False,
        "packages": packages,
        "includes": ["applog", "InputMethodKit", "AppKit", "Foundation"],
        "plist": {
            "CFBundleName": "KorKanaIME",
            "CFBundleDisplayName": "KorKana",
            "CFBundleIdentifier": "org.korkana.inputmethod.KorKanaIME",
            "CFBundleVersion": "0.1.0",
            "CFBundleShortVersionString": "0.1.0",
            "LSUIElement": True,
            "InputMethodConnectionName": "KorKanaIME_Connection",
            "InputMethodServerControllerClass": "KorKanaInputController",
            "TISInputSourceID": "org.korkana.inputmethod.KorKanaIME",
            "TISIntendedLanguage": "ja",
            "tsInputMethodLanguageKey": "ja",
            "tsInputMethodCharacterRepertoireKey": ["Hira", "Kana", "Jpan"],
        },
        "resources": [str(root / "LICENSE"), str(root / "THIRD_PARTY_NOTICES.md"),
                      str(root / "third_party")],
    }},
    setup_requires=["py2app"],
)
