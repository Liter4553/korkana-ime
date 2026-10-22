# -*- coding: utf-8 -*-
"""OS-independent key controller. Output is supplied by each platform adapter."""

import threading

import applog
from . import keys
from .composition import Composition
from .tables import to_katakana

# 핫키 (Ctrl+Alt+?)
HOTKEY_TOGGLE = 0x4A      # J - IME 켜기/끄기
HOTKEY_KANA = 0x4B        # K - 히라가나/가타카나
HOTKEY_QUIT = 0x51        # Q - 종료
HOTKEY_PUNCT = 0x50       # P - 구두점 치환 켜기/끄기

VK_UP, VK_DOWN = 0x26, 0x28
VK_1, VK_9 = 0x31, 0x39

# 일본어 구두점 치환. 전부 Shift 안 누른 상태만 바꾼다
# (Shift 를 누르면 > < { } 라서 그대로 통과시켜야 한다).
PUNCTUATION = {
    0xBE: "。",     # .
    0xBC: "、",     # ,
    0xDB: "「",     # [
    0xDD: "」",     # ]
}

# 그 자체로는 글자를 만들지 않는 키들.
# 이 키들에서 조립 중인 글자를 확정해 버리면 Shift+O(ㅒ) / Shift+P(ㅖ) 처럼
# 수식 키 뒤에 모음이 오는 경우가 깨진다 (냬 -> ん + いぇ).
MODIFIER_VKS = frozenset({
    0x10, 0x11, 0x12,               # Shift, Ctrl, Alt
    0xA0, 0xA1,                     # L/R Shift
    0xA2, 0xA3,                     # L/R Ctrl
    0xA4, 0xA5,                     # L/R Alt
    0x5B, 0x5C,                     # L/R Win
    0x14, 0x90, 0x91,               # CapsLock, NumLock, ScrollLock
    0x15, 0x19,                     # 한/영, 한자
})

# 선택 모드에서 글자 키가 오면 "현재 후보 확정 후 새 입력 시작" 으로 흘려보낸다
_FALLTHROUGH = object()


def _is_text_key(vk: int) -> bool:
    """글자/기호를 찍는 키인가? (방향키·기능키 제외)

    미확정 입력이 있을 때 이런 키는 "삼키고 -> 확정 -> 키 재주입"
    순서로 처리한다. 그냥 통과시키면 물리 키가 주입된 글자보다 먼저 도착해
    순서가 뒤집힐 수 있다.
    """
    return (
        vk in (keys.VK_SPACE, keys.VK_RETURN, keys.VK_TAB)
        or 0x30 <= vk <= 0x39          # 숫자
        or 0x60 <= vk <= 0x6F          # 숫자패드
        or 0xBA <= vk <= 0xC0          # ; = , - . / `
        or 0xDB <= vk <= 0xDF          # [ \ ] 따옴표
        or vk == 0xE2                  # 102키 추가 키
    )


class KoreanKanaIME:
    """키 이벤트를 받아 일본어를 주입하는 상태 기계."""

    def __init__(self, enabled: bool = False, katakana: bool = False,
                 punctuation: bool = True, *, send_text, send_key):
        self._send_text = send_text
        self._send_key = send_key
        self.comp = Composition()
        self.enabled = enabled
        self.katakana = katakana
        self.punctuation = punctuation
        self._lock = threading.Lock()
        self._swallowed = set()        # keydown 을 먹은 키의 keyup 도 먹는다
        self._quit = threading.Event()

    # ------------------------------------------------------------ 상태 조회
    def snapshot(self) -> dict:
        """오버레이가 그릴 내용. 가타카나 모드면 보여줄 때 씌운다."""
        with self._lock:
            comp = self.comp
            reading = comp.display_reading()
            if self.katakana:
                reading = to_katakana(reading)
            return {
                "enabled": self.enabled,
                "katakana": self.katakana,
                "punctuation": self.punctuation,
                "reading": reading,
                "hangul": comp.full_hangul(),
                "candidates": list(comp.cands),
                "index": comp.index,
                "selecting": comp.selecting(),
            }

    def quit_requested(self) -> bool:
        return self._quit.is_set()

    def request_quit(self) -> None:
        self._quit.set()

    def toggle_enabled(self) -> None:
        with self._lock:
            self._commit_locked()
            self.enabled = not self.enabled
        applog.log(f"[IME] {'켜짐' if self.enabled else '꺼짐'}")

    def toggle_katakana(self) -> None:
        with self._lock:
            self._commit_locked()
            self.katakana = not self.katakana
        applog.log(f"[모드] {'가타카나' if self.katakana else '히라가나'}")

    def toggle_punctuation(self) -> None:
        with self._lock:
            self.punctuation = not self.punctuation
        applog.log(f"[구두점] {'。、「」' if self.punctuation else '.,[] 그대로'}")

    def commit(self) -> None:
        """Commit this input context before handing control back to the OS."""
        with self._lock:
            self._commit_locked()

    def reset(self) -> None:
        """Discard preedit when the OS resets or leaves this input context."""
        with self._lock:
            self.comp.clear()
            self._swallowed.clear()

    # ------------------------------------------------------------ 확정
    def _commit_locked(self) -> None:
        """미확정 입력을 대상 앱에 넣는다.

        후보가 선택돼 있으면 그 후보(한자 포함)를 그대로 넣는다.
        후보가 없으면 읽기를 넣고, 가타카나 모드면 이때 씌운다.
        후보 문자열에는 가타카나 변환을 씌우지 않는다 -- 한자가 깨진다.
        """
        if self.comp.is_empty():
            return
        had_candidate = self.comp.selecting()
        text = self.comp.take()
        if self.katakana and not had_candidate:
            text = to_katakana(text)
        self._send_text(text)

    # ------------------------------------------------------------ 키 처리
    def on_key(self, vk, down, shift, ctrl, alt, win) -> bool:
        """훅 콜백. True 를 돌려주면 그 키는 대상 앱에 가지 않는다."""
        if not down:
            # keydown 을 먹었으면 짝이 되는 keyup 도 먹어야 상태가 안 꼬인다
            if vk in self._swallowed:
                self._swallowed.discard(vk)
                return True
            return False

        if self._handle_down(vk, shift, ctrl, alt, win):
            self._swallowed.add(vk)
            return True
        return False

    def _handle_down(self, vk, shift, ctrl, alt, win) -> bool:
        # --- 수식 키 자체는 아무것도 하지 않고 흘려보낸다 (확정도 하지 않는다)
        if vk in MODIFIER_VKS:
            return False

        # --- 핫키는 IME 가 꺼져 있어도 먹는다
        if ctrl and alt and not win:
            if vk == HOTKEY_TOGGLE:
                self.toggle_enabled()
                return True
            if vk == HOTKEY_KANA:
                self.toggle_katakana()
                return True
            if vk == HOTKEY_PUNCT:
                self.toggle_punctuation()
                return True
            if vk == HOTKEY_QUIT:
                self.request_quit()
                return True

        if not self.enabled:
            return False

        # --- 단축키(Ctrl+C 등)는 건드리지 않되, 미확정 입력은 먼저 확정
        if ctrl or alt or win:
            with self._lock:
                self._commit_locked()
            return False

        with self._lock:
            # --- 후보 선택 중이면 그쪽 키맵이 먼저
            if self.comp.selecting():
                result = self._handle_selecting(vk, shift)
                if result is not _FALLTHROUGH:
                    return result
                # _FALLTHROUGH: 후보를 확정했고, 이 키는 새 입력으로 다시 본다

            return self._handle_composing(vk, shift)

    def _handle_selecting(self, vk, shift):
        """후보창이 떠 있을 때의 키맵. _FALLTHROUGH 면 조립 키맵으로 넘긴다."""
        comp = self.comp

        if vk in (keys.VK_SPACE, VK_DOWN):
            comp.move(+1)
            return True
        if vk == VK_UP:
            comp.move(-1)
            return True

        # 숫자키로 바로 고르기
        if VK_1 <= vk <= VK_9:
            if comp.select(vk - VK_1):
                self._commit_locked()
            return True                        # 범위 밖 숫자는 그냥 무시

        if vk == keys.VK_RETURN:
            self._commit_locked()
            return True

        # Esc / Backspace: 후보창만 닫고 읽기로 돌아간다
        if vk in (keys.VK_ESCAPE, keys.VK_BACK):
            comp.cancel_selection()
            return True

        # 그 밖의 키: 현재 후보를 확정하고 그 키를 처리한다
        self._commit_locked()
        if keys.VK_A <= vk <= keys.VK_Z:
            return _FALLTHROUGH                # 글자 키는 새 입력으로 다시 본다
        if self.punctuation and not shift and vk in PUNCTUATION:
            return _FALLTHROUGH                # 구두점은 치환해서 넣어야 한다
        if _is_text_key(vk):
            self._send_key(vk)                 # 확정분보다 먼저 도착하지 않게
            return True
        return False                           # 방향키·기능키는 그대로 통과

    def _handle_composing(self, vk, shift) -> bool:
        """읽기를 조립하는 중의 키맵."""
        comp = self.comp

        # --- 글자 키
        if keys.VK_A <= vk <= keys.VK_Z:
            return comp.feed_key(chr(vk).lower(), shift)

        # --- 백스페이스: 미확정분이 있을 때만 삼킨다
        if vk == keys.VK_BACK:
            return comp.backspace()

        # --- Esc: 미확정 입력 전체 취소
        if vk == keys.VK_ESCAPE:
            if comp.is_empty():
                return False
            comp.clear()
            return True

        # --- 하이픈: 장음 부호 ー
        if vk == keys.VK_OEM_MINUS and not shift:
            comp.feed_choon()
            return True

        # --- 구두점 치환: . , [ ] -> 。、「」
        if self.punctuation and not shift and vk in PUNCTUATION:
            self._commit_locked()
            self._send_text(PUNCTUATION[vk])
            return True

        # --- 스페이스: 한자 변환 시작 (= IME 의 변환키)
        if vk == keys.VK_SPACE:
            if comp.is_empty():
                return False               # 빈 상태면 그냥 공백
            if not self.katakana and comp.start_selection():
                return True
            # 가타카나 모드거나 후보가 없으면 그대로 확정 (공백은 넣지 않는다)
            self._commit_locked()
            return True

        # --- 엔터: 변환 없이 읽기 그대로 확정 (줄바꿈은 넣지 않는다)
        if vk == keys.VK_RETURN:
            if comp.is_empty():
                return False
            self._commit_locked()
            return True

        # --- 그 밖의 글자/기호 키: 확정하고 그 키를 다시 주입 (순서 보장)
        if _is_text_key(vk):
            if comp.is_empty():
                return False
            self._commit_locked()
            self._send_key(vk)
            return True

        # --- 방향키·기능키 등: 확정만 하고 키는 그대로 통과
        self._commit_locked()
        return False
