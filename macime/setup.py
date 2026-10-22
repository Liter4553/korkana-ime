"""Run from the repository root: python macime/setup.py py2app.

This bundles Python and PyObjC, so the installed input source needs no venv.
Build separately on Apple Silicon and Intel; no cross-compilation is implied.
"""

import sys
import subprocess
from pathlib import Path

if sys.platform != "darwin":
    raise SystemExit("KorKanaIME.app must be built on macOS.")

from setuptools import setup
from py2app.build_app import py2app


class KorKanaBuild(py2app):
    def copy_loader_paths(self, sourcefn, destfn):
        super().copy_loader_paths(sourcefn, destfn)
        if not Path(sourcefn).name.startswith("_MeCab."):
            return
        library = Path(destfn).parent / "mecab.dylibs" / "libmecab.2.dylib"
        if not library.is_file() or self.dry_run:
            return
        # The wheel's dylib has too little Mach-O header padding for py2app's
        # long Resources/lib/pythonX.Y/lib-dynload install name. Frameworks is
        # short enough, and keeps both architectures in universal2 wheels.
        contents = next(p for p in Path(destfn).parents if p.name == "Contents")
        frameworks = contents / "Frameworks"
        frameworks.mkdir(exist_ok=True)
        self.copy_file(str(library), str(frameworks / library.name))
        subprocess.run([
            "install_name_tool", "-change",
            "@loader_path/mecab.dylibs/libmecab.2.dylib",
            "@executable_path/../Frameworks/libmecab.2.dylib", str(destfn),
        ], check=True)
        library.unlink()
        library.parent.rmdir()

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
    cmdclass={"py2app": KorKanaBuild},
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
