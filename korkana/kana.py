# -*- coding: utf-8 -*-
"""한글 음절 -> 가나 변환."""

from .tables import (
    CHO, JUNG, JONG, CHO_ROW, JUNG_COL, ROWS, JONG_KANA,
    BARE_CONSONANT_KANA, CHOON, to_katakana,
)

_HANGUL_BASE = 0xAC00
_HANGUL_LAST = 0xD7A3

# 장음 부호로 쓰는 입력 문자들
LONG_VOWEL_KEYS = ("-", "ー", "ㅡㅡ")


def decompose(ch: str):
    """완성형 한글 음절 -> (초성, 중성, 종성 or None). 음절이 아니면 None."""
    code = ord(ch)
    if not (_HANGUL_BASE <= code <= _HANGUL_LAST):
        return None
    idx = code - _HANGUL_BASE
    cho = CHO[idx // 588]
    jung = JUNG[(idx % 588) // 28]
    jong = JONG[idx % 28]
    return cho, jung, (None if jong == "\0" else jong)


def compose(cho: str | None, jung: str | None, jong: str | None) -> str:
    """(초성, 중성, 종성) -> 표시용 문자열. 불완전하면 낱자 그대로."""
    if cho and jung:
        code = (
            _HANGUL_BASE
            + CHO.index(cho) * 588
            + JUNG.index(jung) * 28
            + (JONG.index(jong) if jong else 0)
        )
        return chr(code)
    return (cho or "") + (jung or "") + (jong or "")


def jamo_to_kana(cho: str | None, jung: str | None, jong: str | None) -> str:
    """자모 삼원소 -> 가나(히라가나). 변환 불가한 조각은 낱자 그대로 돌려준다."""
    # 모음이 없는 경우: 받침성 자음 단독
    if jung is None:
        if cho is None:
            return ""
        return BARE_CONSONANT_KANA.get(cho, cho)

    row_key = CHO_ROW.get(cho, "") if cho else ""     # 초성 없는 모음 = あ행
    col_key = JUNG_COL.get(jung)
    if col_key is None:
        return compose(cho, jung, jong)

    row = ROWS.get(row_key)
    if row is None:
        return compose(cho, jung, jong)

    kana = row.get(col_key)
    if kana is None:                                   # 해당 단이 없으면 う단으로 떨어뜨림
        kana = row.get("u", "")

    if jong:
        kana += JONG_KANA.get(jong, "")
    return kana


def syllable_to_kana(ch: str, katakana: bool = False) -> str:
    """한 글자(한글 음절 또는 낱자) -> 가나."""
    parts = decompose(ch)
    if parts is not None:
        out = jamo_to_kana(*parts)
    elif ch in CHO or ch in JUNG:
        # 낱자: 자음은 ん/っ, 모음은 あ행
        out = jamo_to_kana(ch, None, None) if ch in CHO else jamo_to_kana(None, ch, None)
    elif ch == "-":
        out = CHOON
    else:
        return ch                                      # 공백/숫자/기호는 그대로
    return to_katakana(out) if katakana else out


def convert(text: str, katakana: bool = False) -> str:
    """문자열 전체를 가나로. 한글이 아닌 문자는 그대로 통과시킨다('-'는 장음 ー)."""
    return "".join(syllable_to_kana(ch, katakana) for ch in text)
