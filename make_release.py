# -*- coding: utf-8 -*-
"""배포물 만들기.

    python make_release.py

세 단계로 돈다.
  1. 앱을 onedir 로 빌드          -> dist/KorKanaIME/
  2. 그걸 zip 으로 묶어           -> build/payload.zip
  3. 설치 프로그램 안에 넣어 빌드 -> release/KorKanaIME-Setup.exe

결과물은 release/ 에 두 개가 나온다.
  KorKanaIME-Setup.exe       설치 프로그램 (이것만 주면 된다)
  KorKanaIME-portable.zip    설치 없이 압축만 풀어 쓰는 판
"""

import os
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, "dist")
BUILD = os.path.join(ROOT, "build")
RELEASE = os.path.join(ROOT, "release")
APP_DIR = os.path.join(DIST, "KorKanaIME")
PAYLOAD = os.path.join(BUILD, "payload.zip")

SETUP_SPEC = """# -*- mode: python ; coding: utf-8 -*-
# make_release.py 가 자동 생성한다. 직접 고치지 말 것.
a = Analysis(
    [r"{installer}"],
    pathex=[],
    binaries=[],
    datas=[(r"{payload}", "."), (r"{icon}", ".")],
    hiddenimports=[],
    excludes=["numpy", "pandas", "matplotlib", "scipy", "PIL", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="KorKanaIME-Setup",
    debug=False, strip=False, upx=False,
    console=False, icon=r"{icon}",
)
"""


def run(cmd, label):
    print(f"\n=== {label} ===")
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        sys.exit(f"실패: {label}")


def human(path):
    size = (os.path.getsize(path) if os.path.isfile(path) else
            sum(os.path.getsize(os.path.join(r, f))
                for r, _, fs in os.walk(path) for f in fs))
    return f"{size / 1e6:.1f} MB"


def main():
    icon = os.path.join(ROOT, "assets", "icon.ico")
    if not os.path.exists(icon):
        sys.exit("assets/icon.ico 가 없습니다.")

    # 1) 앱 빌드
    run([sys.executable, "-m", "PyInstaller", "KorKanaIME.spec",
         "--noconfirm", "--log-level", "WARN"], "앱 빌드")
    if not os.path.exists(os.path.join(APP_DIR, "KorKanaIME.exe")):
        sys.exit("앱 빌드 결과가 없습니다.")
    print(f"  dist/KorKanaIME  {human(APP_DIR)}")

    # 2) payload.zip
    print("\n=== payload.zip 묶는 중 ===")
    os.makedirs(BUILD, exist_ok=True)
    if os.path.exists(PAYLOAD):
        os.remove(PAYLOAD)
    with zipfile.ZipFile(PAYLOAD, "w", zipfile.ZIP_DEFLATED,
                         compresslevel=6) as zf:
        for root, _, names in os.walk(APP_DIR):
            for name in names:
                full = os.path.join(root, name)
                zf.write(full, os.path.relpath(full, APP_DIR))
    print(f"  {PAYLOAD}  {human(PAYLOAD)}")

    # 3) 설치 프로그램
    spec_path = os.path.join(BUILD, "Setup.spec")
    with open(spec_path, "w", encoding="utf-8") as f:
        f.write(SETUP_SPEC.format(
            installer=os.path.join(ROOT, "installer.py"),
            payload=PAYLOAD, icon=icon))
    run([sys.executable, "-m", "PyInstaller", spec_path,
         "--noconfirm", "--distpath", DIST, "--workpath",
         os.path.join(BUILD, "setup_work"), "--log-level", "WARN"],
        "설치 프로그램 빌드")

    # 4) release/ 로 모으기
    os.makedirs(RELEASE, exist_ok=True)
    setup_src = os.path.join(DIST, "KorKanaIME-Setup.exe")
    setup_dst = os.path.join(RELEASE, "KorKanaIME-Setup.exe")
    if not os.path.exists(setup_src):
        sys.exit("설치 프로그램 빌드 결과가 없습니다.")
    shutil.copy2(setup_src, setup_dst)

    portable = os.path.join(RELEASE, "KorKanaIME-portable.zip")
    if os.path.exists(portable):
        os.remove(portable)
    with zipfile.ZipFile(portable, "w", zipfile.ZIP_DEFLATED,
                         compresslevel=6) as zf:
        for root, _, names in os.walk(APP_DIR):
            for name in names:
                full = os.path.join(root, name)
                zf.write(full, os.path.join(
                    "KorKanaIME", os.path.relpath(full, APP_DIR)))

    print("\n=== 완료 ===")
    for path in (setup_dst, portable):
        print(f"  {os.path.relpath(path, ROOT)}  {human(path)}")


if __name__ == "__main__":
    main()
