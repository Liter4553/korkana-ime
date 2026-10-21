# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 빌드 설정.

    python -m PyInstaller KorKanaIME.spec --noconfirm

onedir 로 묶는다. onefile 은 실행할 때마다 Mozc 사전(97MB)을 임시 폴더에
통째로 풀기 때문에 시작이 몇 초씩 걸린다. 설치해 두고 쓰는 프로그램이라
onedir 가 맞다.

콘솔은 없앤다(console=False). 배경에서 도는 입력기라 검은 창이 떠 있을
이유가 없다. 대신 출력은 전부 applog 가 파일로 남긴다.
"""

from PyInstaller.utils.hooks import collect_data_files

# mozcpy 의 사전 파일(dic/sys.dic, dic/matrix.bin)은 자동으로 안 딸려온다
mozc_data = collect_data_files("mozcpy")

a = Analysis(
    ["ime.py"],
    pathex=[],
    binaries=[],
    # 사전을 같이 배포하므로 그 라이선스 고지도 반드시 동봉해야 한다
    # (Mozc 는 BSD-3, 사전 부분은 ICOT 의 NO WARRANTY 첨부 조건이 붙는다)
    datas=mozc_data + [
        ("README.md", "."),
        ("LICENSE", "."),
        ("THIRD_PARTY_NOTICES.md", "."),
        ("third_party/mozc-LICENSE.txt", "third_party"),
        ("third_party/mozcpy-LICENSE.txt", "third_party"),
    ],
    hiddenimports=["mozcpy"],
    hookspath=[],
    runtime_hooks=[],
    # 안 쓰는 큰 덩어리는 빼서 용량을 줄인다
    excludes=[
        "numpy", "pandas", "matplotlib", "scipy", "PIL",
        "pytest", "setuptools", "pip", "unittest", "email",
        "html", "http", "xml", "pydoc_data",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="KorKanaIME",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,              # 배경 입력기 - 콘솔 없음
    disable_windowed_traceback=False,
    icon="assets/icon.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="KorKanaIME",
)
