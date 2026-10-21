# -*- coding: utf-8 -*-
"""미확정 입력 하나(한 문구)를 관리한다.

한자 변환이 들어오면서 커밋 모델이 바뀌었다.
  이전: 음절이 완성되는 즉시 커밋 (미확정 = 한 음절 이하)
  지금: 확정(Enter) 또는 후보 선택까지 문구 전체를 들고 있는다

세 겹으로 쌓인다.

    두벌식 낱자 ──> HangulComposer ──> 한글 음절
                                         │ convert()
                                         ▼
                    읽기 (히라가나) ──> candidates() ──> 후보 목록

확정된 음절은 **(한글, 가나) 쌍**으로 쌓는다. 가나만 들고 있으면 사용자가
지금 한국어로 뭘 치고 있는지 되돌려 보여줄 수 없기 때문이다.
한 음절이 가나 두 자가 되는 경우(쿄 -> きょ, 킷 -> きっ)가 있어서 두 줄을
따로 세면 어긋난다.

읽기는 **항상 히라가나**로 들고 있는다. Mozc 사전이 히라가나를 받고,
가타카나 변환은 보여줄 때/확정할 때만 씌우면 되기 때문이다.
"""

from .jamo import HangulComposer
from .kana import convert
from .kanji import candidates
from .tables import CHOON

_CHOON_KEY = "-"       # 장음 부호를 넣은 자리에 한글 대신 보여줄 것


class Composition:
    """조립 중인 한글 음절 + 확정된 (한글, 가나) 쌍들 + 한자 후보."""

    def __init__(self):
        self.composer = HangulComposer()
        self.segments = []         # [(한글, 가나)] - 확정된 음절들
        self.cands = []            # 후보 목록 (선택 모드일 때만 채워진다)
        self.index = 0             # 선택된 후보

    # ------------------------------------------------------------ 상태
    def is_empty(self) -> bool:
        return not self.segments and self.composer.is_empty()

    def selecting(self) -> bool:
        """후보 선택 중인가?"""
        return bool(self.cands)

    def settled_reading(self) -> str:
        """확정된 음절들의 가나."""
        return "".join(kana for _, kana in self.segments)

    def _pending_kana(self) -> str:
        pending = self.composer.pending()
        return convert(pending) if pending else ""

    def full_reading(self) -> str:
        """조립 중인 음절까지 포함한 전체 읽기. 변환·확정에 쓴다."""
        return self.settled_reading() + self._pending_kana()

    def display_reading(self) -> str:
        """오버레이에 보여줄 읽기.

        모음이 아직 안 온 낱자는 가나 줄에서 뺀다. 한글 줄에 이미 보이니
        중복이고, 읽기로서도 의미가 없다. 특히 홀로 있는 ㅇ 은 모음 음절의
        시작이지 ん 이 아니라서(아/이/우...), 그대로 두면 틀린 읽기가 된다.
        중성이 있으면 변환은 언제나 순수 가나로 떨어진다.
        """
        if self.composer.jung is None:
            return self.settled_reading()
        return self.settled_reading() + self._pending_kana()

    def full_hangul(self) -> str:
        """지금 치고 있는 한글 전체(표시용). 조립 중인 음절까지 포함."""
        return "".join(h for h, _ in self.segments) + self.composer.pending()

    def current(self) -> str:
        """지금 확정하면 나올 문자열."""
        if self.cands:
            return self.cands[self.index]
        return self.full_reading()

    # ------------------------------------------------------------ 입력
    def _settle_pending(self) -> None:
        """조립 중인 음절을 확정 목록으로 넘긴다."""
        pending = self.composer.pending()
        if pending:
            self.segments.append((pending, convert(pending)))
        self.composer.clear()

    def feed_key(self, letter: str, shift: bool = False) -> bool:
        """영문 글자 하나. 두벌식 낱자가 아니면 False."""
        done, handled = self.composer.feed_key(letter, shift)
        if not handled:
            return False
        for syllable in done:
            self.segments.append((syllable, convert(syllable)))
        return True

    def feed_choon(self) -> None:
        """장음 부호 ー 를 넣는다. 조립 중인 음절은 먼저 확정한다."""
        self._settle_pending()
        self.segments.append((_CHOON_KEY, CHOON))

    def backspace(self) -> bool:
        """조립 중이면 낱자 하나, 아니면 확정된 음절 하나를 지운다.

        음절 단위로 지운다. 가나 한 자씩 지우면 쿄(きょ) 같은 음절이 반쪽만
        남아서 한글 쪽과 어긋난다.
        """
        if self.composer.backspace():
            return True
        if self.segments:
            self.segments.pop()
            return True
        return False

    # ------------------------------------------------------------ 후보 선택
    def start_selection(self) -> bool:
        """조립 중인 음절을 확정하고 후보를 띄운다."""
        self._settle_pending()
        reading = self.settled_reading()
        if not reading:
            return False
        self.cands = candidates(reading)
        self.index = 0
        return bool(self.cands)

    def cancel_selection(self) -> None:
        """후보창을 닫고 읽기 상태로 돌아간다 (읽기는 남는다)."""
        self.cands = []
        self.index = 0

    def move(self, delta: int) -> None:
        """후보를 옮긴다. 양 끝에서 순환한다."""
        if self.cands:
            self.index = (self.index + delta) % len(self.cands)

    def select(self, index: int) -> bool:
        """후보를 번호로 고른다. 범위를 벗어나면 False."""
        if 0 <= index < len(self.cands):
            self.index = index
            return True
        return False

    # ------------------------------------------------------------ 종료
    def clear(self) -> None:
        self.composer.clear()
        self.segments = []
        self.cands = []
        self.index = 0

    def take(self) -> str:
        """확정 문자열을 꺼내고 비운다."""
        out = self.current()
        self.clear()
        return out
