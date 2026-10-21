# -*- coding: utf-8 -*-
"""두벌식 QWERTY -> 한글 낱자 -> 음절 조립 오토마타.

윈도우 한국어 IME를 켜지 않고도 영문 자리에서 바로 치기 위한 계층이다.
    "gkwlapakdlteh"  ->  하 지 메 마 시 떼
음절이 확정될 때마다 그 음절을 내보내므로, 상위 IME 는 그것을 가나로 바꿔
즉시 커밋할 수 있다(미확정 글자는 항상 한 음절 이하).
"""

from .tables import CONSONANTS, VOWELS
from .kana import compose

# ---------------------------------------------------------------- 두벌식 자리
_BASE = {
    "q": "ㅂ", "w": "ㅈ", "e": "ㄷ", "r": "ㄱ", "t": "ㅅ",
    "y": "ㅛ", "u": "ㅕ", "i": "ㅑ", "o": "ㅐ", "p": "ㅔ",
    "a": "ㅁ", "s": "ㄴ", "d": "ㅇ", "f": "ㄹ", "g": "ㅎ",
    "h": "ㅗ", "j": "ㅓ", "k": "ㅏ", "l": "ㅣ",
    "z": "ㅋ", "x": "ㅌ", "c": "ㅊ", "v": "ㅍ",
    "b": "ㅠ", "n": "ㅜ", "m": "ㅡ",
}
_SHIFTED = {
    "q": "ㅃ", "w": "ㅉ", "e": "ㄸ", "r": "ㄲ", "t": "ㅆ",
    "o": "ㅒ", "p": "ㅖ",
}


def key_to_jamo(letter: str, shift: bool = False) -> str | None:
    """영문 글자 하나 -> 두벌식 낱자. 해당 없으면 None."""
    letter = letter.lower()
    if shift and letter in _SHIFTED:
        return _SHIFTED[letter]
    return _BASE.get(letter)


# ---------------------------------------------------------------- 결합 규칙
_JUNG_COMBO = {
    ("ㅗ", "ㅏ"): "ㅘ", ("ㅗ", "ㅐ"): "ㅙ", ("ㅗ", "ㅣ"): "ㅚ",
    ("ㅜ", "ㅓ"): "ㅝ", ("ㅜ", "ㅔ"): "ㅞ", ("ㅜ", "ㅣ"): "ㅟ",
    ("ㅡ", "ㅣ"): "ㅢ",
}
_JONG_COMBO = {
    ("ㄱ", "ㅅ"): "ㄳ", ("ㄴ", "ㅈ"): "ㄵ", ("ㄴ", "ㅎ"): "ㄶ",
    ("ㄹ", "ㄱ"): "ㄺ", ("ㄹ", "ㅁ"): "ㄻ", ("ㄹ", "ㅂ"): "ㄼ",
    ("ㄹ", "ㅅ"): "ㄽ", ("ㄹ", "ㅌ"): "ㄾ", ("ㄹ", "ㅍ"): "ㄿ",
    ("ㄹ", "ㅎ"): "ㅀ", ("ㅂ", "ㅅ"): "ㅄ",
}
# 되돌리기용 역테이블
_JUNG_SPLIT = {v: k for k, v in _JUNG_COMBO.items()}
_JONG_SPLIT = {v: k for k, v in _JONG_COMBO.items()}

# 종성으로 쓸 수 없는 자음 (쌍자음 중 ㄸㅃㅉ)
_NOT_JONG = {"ㄸ", "ㅃ", "ㅉ"}


class HangulComposer:
    """낱자를 받아 음절을 조립한다.

    feed() 는 *확정된* 음절들의 리스트를 돌려주고,
    미확정 음절은 pending() 으로 볼 수 있다.
    """

    def __init__(self) -> None:
        self.cho: str | None = None
        self.jung: str | None = None
        self.jong: str | None = None

    # ------------------------------------------------------------ 상태
    def is_empty(self) -> bool:
        return self.cho is None and self.jung is None and self.jong is None

    def pending(self) -> str:
        """조립 중인 글자(표시용)."""
        return compose(self.cho, self.jung, self.jong)

    def _reset(self) -> None:
        self.cho = self.jung = self.jong = None

    def _take(self) -> str:
        """현재 상태를 확정해 내보내고 비운다."""
        out = self.pending()
        self._reset()
        return out

    def clear(self) -> None:
        """조립 중인 글자를 버린다(Esc, 포커스 이동)."""
        self._reset()

    def flush(self) -> str:
        """조립 중인 글자를 강제 확정(스페이스/엔터/포커스 이동 시)."""
        return self._take() if not self.is_empty() else ""

    # ------------------------------------------------------------ 입력
    def feed(self, jamo: str) -> list[str]:
        """낱자 하나를 넣는다. 확정된 음절 리스트를 돌려준다."""
        if jamo in VOWELS:
            return self._feed_vowel(jamo)
        if jamo in CONSONANTS:
            return self._feed_consonant(jamo)
        # 알 수 없는 낱자: 조립 중인 것을 확정하고 그대로 흘린다
        out = [self._take()] if not self.is_empty() else []
        return out + [jamo]

    def _feed_vowel(self, v: str) -> list[str]:
        if self.jung is None:
            # 초성만 있거나 아무것도 없는 상태 -> 중성 자리에 꽂는다
            self.jung = v
            return []

        if self.jong is None:
            combo = _JUNG_COMBO.get((self.jung, v))
            if combo:
                self.jung = combo
                return []
            return [self._take()] + self._start_with_vowel(v)

        # 받침이 있는데 모음이 왔다: 받침 마지막 조각이 다음 음절 초성으로 넘어간다
        #   하 + ㅈ -> 핮,  + ㅣ -> 하 확정 + 지
        head, moved = self._split_jong()
        self.jong = head
        done = self._take()
        self.cho, self.jung, self.jong = moved, v, None
        return [done]

    def _start_with_vowel(self, v: str) -> list[str]:
        self.jung = v
        return []

    def _split_jong(self) -> tuple[str | None, str]:
        """종성을 (남길 것, 넘길 것) 으로 쪼갠다."""
        pair = _JONG_SPLIT.get(self.jong)
        if pair:
            return pair[0], pair[1]
        return None, self.jong

    def _feed_consonant(self, c: str) -> list[str]:
        if self.jung is None:
            if self.cho is None:
                self.cho = c
                return []
            # 자음 뒤에 또 자음: 앞 자음을 확정하고 새로 시작
            done = self._take()
            self.cho = c
            return [done]

        if self.jong is None:
            # 초성 없는 모음(ㅏ, ㅣ...)에는 받침을 붙일 수 없다.
            # 실제 한국어 IME 처럼 모음을 확정하고 새 음절을 시작한다.
            if c in _NOT_JONG or self.cho is None:
                done = self._take()
                self.cho = c
                return [done]
            self.jong = c
            return []

        combo = _JONG_COMBO.get((self.jong, c))
        if combo:
            self.jong = combo
            return []
        done = self._take()
        self.cho = c
        return [done]

    def feed_key(self, letter: str, shift: bool = False) -> tuple[list[str], bool]:
        """영문 글자 하나를 넣는다. (확정 음절들, 처리했는지) 를 돌려준다."""
        jamo = key_to_jamo(letter, shift)
        if jamo is None:
            return [], False
        return self.feed(jamo), True

    # ------------------------------------------------------------ 백스페이스
    def backspace(self) -> bool:
        """조립 중인 글자에서 낱자 하나를 지운다. 지울 게 없으면 False."""
        if self.jong is not None:
            pair = _JONG_SPLIT.get(self.jong)
            self.jong = pair[0] if pair else None
            return True
        if self.jung is not None:
            pair = _JUNG_SPLIT.get(self.jung)
            self.jung = pair[0] if pair else None
            return True
        if self.cho is not None:
            self.cho = None
            return True
        return False
