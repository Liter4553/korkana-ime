# -*- coding: utf-8 -*-
"""korkana - 한국어 발음 표기를 일본어로 바꾸는 변환 엔진.

Windows 와 무관한 순수 Python 이라 따로 가져다 쓸 수 있다.

    from korkana import convert, candidates
    convert("하지메마시떼")          # はじめまして
    candidates("わたしはがくせいです")  # ['私は学生です', ...]
"""

from .kana import convert, syllable_to_kana, jamo_to_kana, compose, decompose
from .tables import to_katakana
from .jamo import HangulComposer, key_to_jamo
from .kanji import candidates, available as kanji_available, dict_info
from .composition import Composition

__all__ = [
    "convert", "syllable_to_kana", "jamo_to_kana", "compose", "decompose",
    "to_katakana", "HangulComposer", "key_to_jamo",
    "candidates", "kanji_available", "dict_info", "Composition",
]
