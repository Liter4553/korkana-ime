# -*- coding: utf-8 -*-
"""가나(히라가나) -> 한자 후보 변환.

Mozc(구글 일본어 입력)의 사전을 쓰는 mozcpy 를 감싼다.
mozcpy 가 없어도 import 는 성공하고, 그 경우 후보는 읽기 그대로 하나만 나온다.
즉 사전이 없으면 가나 입력기로 동작하고, 있으면 한자 변환까지 된다.
"""

import os

MAX_CANDIDATES = 9          # 1~9 숫자키로 고를 수 있는 만큼
_MAX_READING = 60           # 너무 긴 입력은 변환을 시도하지 않는다

_converter = None
_load_error = None
_loaded = False


def _load():
    """mozcpy 를 처음 쓸 때 한 번만 올린다."""
    global _converter, _load_error, _loaded
    if _loaded:
        return _converter
    _loaded = True
    try:
        import mozcpy
        if os.name == "posix":
            # mozcpy 0.3 builds an unquoted MeCab command line. macOS installs
            # input methods under "Input Methods", so quote the dictionary path.
            from mozcpy import mozcpy as backend
            directory = backend.DICT_DIR.replace("\\", "\\\\").replace('"', '\\"')
            backend.MECAB_ARGS = f'-d "{directory}" -r /dev/null'
        _converter = mozcpy.Converter()
    except Exception as exc:
        _converter = None
        _load_error = exc
    return _converter


def available() -> bool:
    """한자 변환을 쓸 수 있는가?"""
    return _load() is not None


def dict_info() -> str:
    """사전 상태를 사람이 읽을 문장으로."""
    conv = _load()
    if conv is None:
        return f"한자 변환 없음 (mozcpy 미설치: {_load_error})"
    try:
        return f"Mozc 사전 {conv.dict_version()}"
    except Exception:
        return "Mozc 사전"


def candidates(reading: str, limit: int = MAX_CANDIDATES) -> list:
    """히라가나 읽기 -> 후보 목록.

    항상 읽기 자체를 후보에 포함시키고(한자를 원하지 않을 수도 있으니),
    중복은 순서를 지키며 걸러낸다. 첫 번째가 기본 선택이다.
    """
    reading = reading.strip()
    if not reading:
        return []

    found = []
    conv = _load()
    if conv is not None and len(reading) <= _MAX_READING:
        try:
            found = conv.convert(reading, n_best=limit) or []
        except Exception:
            found = []                      # 변환 실패는 치명적이지 않다

    out = []
    for cand in list(found) + [reading]:
        if cand and cand not in out:
            out.append(cand)
    return out[:limit]
