"""Install an IBus engine in the current user's XDG data directory.

Use a system Python or a venv created with --system-site-packages so gi and IBus
are visible. The source tree can be moved after installation; the selected
Python environment must remain in place.
"""

import argparse
import os
import shlex
import shutil
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

from linuxime.engine import BUS_NAME, ENGINE_NAME


def component_xml(launcher):
    component = ET.Element("component")
    values = {
        "name": BUS_NAME, "description": "KorKana Japanese IME",
        "exec": shlex.join([str(launcher), "--ibus"]), "version": "0.1.0",
        "author": "KorKana contributors", "license": "MIT",
        "homepage": "https://github.com/Liter4553/korkana-ime",
        "textdomain": "",
    }
    for name, value in values.items():
        ET.SubElement(component, name).text = value
    engine = ET.SubElement(ET.SubElement(component, "engines"), "engine")
    for name, value in {
        "name": ENGINE_NAME, "longname": "KorKana", "language": "ja",
        "license": "MIT", "author": "KorKana contributors", "layout": "us",
        "symbol": "あ", "description": "두벌식 한글 발음 일본어 입력기",
    }.items():
        ET.SubElement(engine, name).text = value
    return ET.tostring(component, encoding="unicode", xml_declaration=True)


def install(data_dir, python):
    source = Path(__file__).resolve().parents[1]
    destination = data_dir / "korkana-ime"
    # Never recursively copy the source tree into itself.
    if destination == source or source in destination.parents:
        raise ValueError("Installation directory must be outside the source tree")
    destination.mkdir(parents=True, exist_ok=True)
    for package in ("korkana", "linuxime", "third_party"):
        shutil.copytree(source / package, destination / package, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in ("applog.py", "LICENSE", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(source / name, destination / name)
    launcher = destination / "ibus-engine-korkana"
    launcher.write_text(
        "#!/bin/sh\ncd " + shlex.quote(str(destination)) + " || exit 1\nexec " +
        shlex.quote(str(python)) + " -m linuxime.engine \"$@\"\n", encoding="utf-8")
    launcher.chmod(0o755)
    component_dir = data_dir / "ibus" / "component"
    component_dir.mkdir(parents=True, exist_ok=True)
    descriptor = component_dir / "korkana.xml"
    descriptor.write_text(component_xml(launcher), encoding="utf-8")
    return descriptor


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path,
                        default=Path(os.environ.get("XDG_DATA_HOME") or
                                     Path.home() / ".local" / "share"))
    args = parser.parse_args(argv)
    if sys.platform != "linux":
        parser.error("Run this installer on Linux")
    try:
        import gi
        gi.require_version("IBus", "1.0")
        from gi.repository import IBus
    except (ImportError, ValueError) as exc:
        parser.error(f"IBus/PyGObject 필요: {exc}. docs/PORTING.md 참고")
    descriptor = install(args.data_dir.expanduser().resolve(), Path(sys.executable))
    print(f"사용자 폴더에 설치됨: {descriptor}\n"
          "IBus는 기본적으로 시스템 component 폴더만 검색합니다. 다음을 실행하세요:\n"
          f"sudo install -m 644 {shlex.quote(str(descriptor))} "
          "/usr/share/ibus/component/korkana.xml\n"
          "그런 다음 로그아웃/로그인하고 일본어 입력 소스에서 KorKana를 선택하세요.\n"
          "관리자 권한 없는 임시 실행: python -m linuxime.engine (docs/PORTING.md 참고)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
