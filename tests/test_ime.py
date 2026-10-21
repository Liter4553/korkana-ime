# -*- coding: utf-8 -*-
"""컨트롤러(키 처리 + 한자 후보) 테스트. 실제 훅 없이 키 이벤트만 주입한다.

실행: python tests/test_ime.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from winime import winapi

# SendInput 을 실제로 쏘지 않도록 먼저 갈아끼운다
SENT = []
VKS = []
winapi.send_text = lambda text: SENT.append(text)
winapi.send_vk = lambda vk: VKS.append(vk)
winapi.foreground_window = lambda: 0x1234

import ime as ime_mod
from korkana import kanji

VK_BACK = 0x08
VK_RETURN = 0x0D
VK_SHIFT = 0x10
VK_ESC = 0x1B
VK_SPACE = 0x20
VK_LEFT = 0x25
VK_UP, VK_DOWN = 0x26, 0x28
VK_MINUS = 0xBD
VK_PERIOD = 0xBE
VK_COMMA = 0xBC
VK_LBRACKET = 0xDB
VK_RBRACKET = 0xDD


class Keyboard:
    """키 시퀀스를 IME 에 먹여 주는 헬퍼."""

    def __init__(self, enabled=True, katakana=False, punctuation=True):
        self.ime = ime_mod.KoreanKanaIME(
            enabled=enabled, katakana=katakana, punctuation=punctuation)
        self.shift = False
        SENT.clear()
        VKS.clear()

    def press(self, vk, shift=None):
        """keydown + keyup 한 쌍. (삼켰는지 여부) 반환."""
        s = self.shift if shift is None else shift
        swallowed = self.ime.on_key(vk, True, s, False, False, False)
        self.ime.on_key(vk, False, s, False, False, False)
        return swallowed

    def type_keys(self, keys: str):
        """대문자는 Shift 키 눌림까지 실제로 흉내낸다."""
        for ch in keys:
            if ch.isupper():
                self.shift = True
                self.ime.on_key(VK_SHIFT, True, True, False, False, False)
                self.press(ord(ch))
                self.ime.on_key(VK_SHIFT, False, True, False, False, False)
                self.shift = False
            else:
                self.press(ord(ch.upper()))

    def hotkey(self, vk):
        self.ime.on_key(vk, True, False, True, True, False)
        self.ime.on_key(vk, False, False, True, True, False)

    # --- 상태 조회
    def committed(self) -> str:
        return "".join(SENT)

    def vks(self) -> list:
        return list(VKS)

    def snap(self) -> dict:
        return self.ime.snapshot()

    def reading(self) -> str:
        return self.snap()["reading"]

    def hangul(self) -> str:
        return self.snap()["hangul"]

    def cands(self) -> list:
        return self.snap()["candidates"]

    def chosen(self):
        s = self.snap()
        return s["candidates"][s["index"]] if s["candidates"] else None


def run():
    fails = []

    def check(label, got, want):
        if got != want:
            fails.append(f"{label}: {got!r}, 기대 {want!r}")

    def check_in(label, needle, haystack):
        if needle not in haystack:
            fails.append(f"{label}: {needle!r} 가 {haystack!r} 에 없음")

    has_dict = kanji.available()
    print(f"사전: {kanji.dict_info()}")

    # ---------------------------------------------------- 치는 동안은 커밋 안 됨
    kb = Keyboard()
    kb.type_keys("dhkxktlgk")                      # 와타시하
    check("치는 동안 커밋 없음", kb.committed(), "")
    check("읽기 누적", kb.reading(), "わたしは")
    check("후보창 닫힘", kb.cands(), [])

    # ---------------------------------------------------- Enter = 가나로 확정
    kb.press(VK_RETURN)
    check("Enter 로 가나 확정", kb.committed(), "わたしは")
    check("확정 후 비어 있음", kb.reading(), "")
    check("Enter 는 줄바꿈을 넣지 않는다", kb.vks(), [])

    # ---------------------------------------------------- Space = 한자 변환
    if has_dict:
        kb = Keyboard()
        kb.type_keys("dhkxktlgkrkzntpdleptm")       # 와타시하가쿠세이데스
        check("읽기", kb.reading(), "わたしはがくせいです")
        check("변환 전 커밋 없음", kb.committed(), "")
        check("Space 는 삼킨다", kb.press(VK_SPACE), True)
        cands = kb.cands()
        check("후보가 떴다", len(cands) > 0, True)
        check_in("기대 후보", "私は学生です", cands)
        check("읽기도 후보에 포함", "わたしはがくせいです" in cands, True)
        check("변환만으로는 커밋 안 됨", kb.committed(), "")

        # Space 를 더 누르면 다음 후보
        first = kb.chosen()
        kb.press(VK_SPACE)
        check("Space 로 다음 후보", kb.chosen() != first, True)
        kb.press(VK_UP)
        check("위 화살표로 되돌아옴", kb.chosen(), first)

        # Enter 로 선택된 후보 확정
        kb.press(VK_RETURN)
        check("후보 확정", kb.committed(), first)
        check("확정 후 비어 있음", (kb.reading(), kb.cands()), ("", []))

        # ------------------------------------------------ 숫자키로 바로 고르기
        kb = Keyboard()
        kb.type_keys("xhdnzydn")                    # 토우쿄우
        check("토우쿄우 읽기", kb.reading(), "とうきょう")
        kb.press(VK_SPACE)
        cands = kb.cands()
        check_in("東京 후보", "東京", cands)
        idx = cands.index("東京")
        check("숫자키는 삼킨다", kb.press(0x31 + idx), True)
        check("숫자키로 확정", kb.committed(), "東京")

        # 범위 밖 숫자는 무시 (확정도 통과도 하지 않는다)
        kb = Keyboard()
        kb.type_keys("xhdnzydn")
        kb.press(VK_SPACE)
        n = len(kb.cands())
        if n < 9:
            check("범위 밖 숫자는 삼키고 무시", kb.press(0x31 + n), True)
            check("범위 밖 숫자로 커밋 안 됨", kb.committed(), "")

        # ------------------------------------------------ Esc 는 후보창만 닫는다
        kb = Keyboard()
        kb.type_keys("xhdnzydn")
        kb.press(VK_SPACE)
        check("Esc 삼킴", kb.press(VK_ESC), True)
        check("후보창 닫힘", kb.cands(), [])
        check("읽기는 남는다", kb.reading(), "とうきょう")
        check("Esc 로 커밋 안 됨", kb.committed(), "")
        check("한 번 더 Esc 로 입력 취소", kb.press(VK_ESC), True)
        check("전부 비었다", (kb.reading(), kb.committed()), ("", ""))

        # ------------------------------------------------ 선택 중 Backspace
        kb = Keyboard()
        kb.type_keys("xhdnzydn")
        kb.press(VK_SPACE)
        kb.press(VK_BACK)
        check("Backspace 로 후보창 닫힘", kb.cands(), [])
        check("읽기는 그대로", kb.reading(), "とうきょう")

        # ------------------------------------------------ 선택 중 글자 키
        kb = Keyboard()
        kb.type_keys("xhdnzydn")
        kb.press(VK_SPACE)
        chosen = kb.chosen()
        kb.type_keys("gk")                         # 하
        check("후보 확정됨", kb.committed(), chosen)
        check("새 입력 시작", kb.reading(), "は")

        # ------------------------------------------------ 선택 중 기호 키는 재주입
        # (구두점 치환을 끈 상태. 켜져 있으면 . 은 。 로 바뀐다 - 아래 따로 검사)
        kb = Keyboard(punctuation=False)
        kb.type_keys("xhdnzydn")
        kb.press(VK_SPACE)
        chosen = kb.chosen()
        check("기호 키 삼킴", kb.press(VK_PERIOD), True)
        check("후보 먼저 확정", kb.committed(), chosen)
        check("기호 키 재주입", kb.vks(), [VK_PERIOD])

        # ------------------------------------------------ 선택 중 방향키는 통과
        kb = Keyboard()
        kb.type_keys("xhdnzydn")
        kb.press(VK_SPACE)
        chosen = kb.chosen()
        check("방향키는 통과", kb.press(VK_LEFT), False)
        check("통과 전에 확정", kb.committed(), chosen)
        check("방향키 재주입 없음", kb.vks(), [])
    else:
        print("  (mozcpy 없음 - 한자 후보 테스트 건너뜀)")

    # ---------------------------------------------------- 사전이 없어도 가나는 보장
    check("후보에 읽기 포함", "とうきょう" in kanji.candidates("とうきょう"), True)
    check("빈 읽기는 후보 없음", kanji.candidates(""), [])

    # ---------------------------------------------------- Shift 뒤 모음 (회귀)
    # s + Shift+O = ㄴ + ㅒ = 냬.  Shift keydown 에서 조기 확정되면 깨진다.
    kb = Keyboard()
    kb.type_keys("sO")
    check("Shift 모음", kb.reading(), "にぇ")
    check("Shift 중엔 커밋 없음", kb.committed(), "")

    # ---------------------------------------------------- 치고 있는 한글 표시
    kb = Keyboard()
    kb.type_keys("dhkxktlgk")                      # 와타시하
    check("한글도 같이 보인다", kb.hangul(), "와타시하")
    check("가나도 같이 보인다", kb.reading(), "わたしは")

    # 모음이 아직 안 온 낱자는 한글 줄에만 보이고 가나 줄에는 안 보인다
    kb = Keyboard()
    kb.type_keys("w")                              # ㅈ
    check("낱자는 한글 줄에", kb.hangul(), "ㅈ")
    check("낱자는 가나 줄에 안 보인다", kb.reading(), "")
    kb.type_keys("l")                              # 지
    check("모음이 오면", (kb.hangul(), kb.reading()), ("지", "じ"))

    # 장음 부호는 한글 줄에 하이픈으로
    kb = Keyboard()
    kb.type_keys("fk")
    kb.press(VK_MINUS)
    kb.type_keys("aps")
    check("장음 한글 표시", kb.hangul(), "라-멘")
    check("장음 가나 표시", kb.reading(), "らーめん")

    # ---------------------------------------------------- 백스페이스 (음절 단위)
    kb = Keyboard()
    kb.type_keys("gkwl")                           # 하지
    check("하지", (kb.hangul(), kb.reading()), ("하지", "はじ"))
    check("낱자 삭제 삼킴", kb.press(VK_BACK), True)
    check("조립 중인 음절은 낱자씩", (kb.hangul(), kb.reading()), ("하ㅈ", "は"))
    check("또 삭제", kb.press(VK_BACK), True)
    check("확정 음절은 통째로 지워진다", (kb.hangul(), kb.reading()), ("하", "は"))
    check("또 삭제", kb.press(VK_BACK), True)
    check("비었다", (kb.hangul(), kb.reading()), ("", ""))
    check("빈 상태 백스페이스는 통과", kb.press(VK_BACK), False)
    check("백스페이스로 커밋 없음", kb.committed(), "")

    # 가나 두 자가 되는 음절도 통째로 지워진다 (쿄 -> きょ)
    kb = Keyboard()
    kb.type_keys("zydn")                           # 쿄우
    check("쿄우", (kb.hangul(), kb.reading()), ("쿄우", "きょう"))
    kb.press(VK_BACK)                              # 조립 중인 우 -> ㅇ
    kb.press(VK_BACK)                              # 우 사라짐
    check("쿄만 남음", (kb.hangul(), kb.reading()), ("쿄", "きょ"))
    kb.press(VK_BACK)
    check("きょ 는 반쪽이 안 남는다", (kb.hangul(), kb.reading()), ("", ""))

    # ---------------------------------------------------- 초성 없는 모음 + 자음
    # ㅣ 뒤에 ㄷ 이 오면 받침이 아니라 새 음절의 초성이어야 한다 (ㅣㄷ 금지)
    kb = Keyboard()
    kb.type_keys("lep")                            # ㅣ + 데
    check("초성 없는 모음은 받침을 받지 않는다", kb.reading(), "いで")

    # ---------------------------------------------------- 장음 확정
    kb = Keyboard()
    kb.type_keys("fk")
    kb.press(VK_MINUS)
    kb.type_keys("aps")
    kb.press(VK_RETURN)
    check("らーめん 확정", kb.committed(), "らーめん")

    # ---------------------------------------------------- 가타카나 모드
    kb = Keyboard(katakana=True)
    kb.type_keys("fk")
    kb.press(VK_MINUS)
    kb.type_keys("aps")
    check("가타카나로 표시", kb.reading(), "ラーメン")
    check("가타카나 모드 Space 는 삼킨다", kb.press(VK_SPACE), True)
    check("가타카나는 후보 없이 확정", kb.committed(), "ラーメン")
    check("가타카나 모드엔 후보창 없음", kb.cands(), [])

    # ---------------------------------------------------- 구두점 치환
    kb = Keyboard()
    kb.type_keys("gk")
    check("구두점 키 삼킴", kb.press(VK_PERIOD), True)
    check("확정분 + 。", kb.committed(), "は。")
    check("재주입은 안 한다", kb.vks(), [])

    kb = Keyboard()
    check("빈 상태에서도 치환", kb.press(VK_COMMA), True)
    check("、 만 들어간다", kb.committed(), "、")

    kb = Keyboard()
    kb.press(VK_LBRACKET)
    kb.press(VK_RBRACKET)
    check("괄호 치환", kb.committed(), "「」")

    # Shift 를 누르면 > < { } 이므로 건드리지 않는다
    kb = Keyboard()
    check("Shift+. 는 통과", kb.press(VK_PERIOD, shift=True), False)
    check("Shift 는 치환 안 함", kb.committed(), "")

    # 후보 선택 중에도 확정 후 치환
    if has_dict:
        kb = Keyboard()
        kb.type_keys("xhdnzydn")
        kb.press(VK_SPACE)
        chosen = kb.chosen()
        check("선택 중 구두점 삼킴", kb.press(VK_PERIOD), True)
        check("후보 확정 + 。", kb.committed(), chosen + "。")
        check("선택 중에도 재주입 없음", kb.vks(), [])

    # 꺼 두면 원래대로 (삼키고 재주입)
    kb = Keyboard(punctuation=False)
    kb.type_keys("gk")
    check("꺼짐: 기호 키 삼킴", kb.press(VK_PERIOD), True)
    check("꺼짐: 확정만", kb.committed(), "は")
    check("꺼짐: 기호 키 재주입", kb.vks(), [VK_PERIOD])

    kb = Keyboard(punctuation=False)
    check("꺼짐: 빈 상태 기호 키는 통과", kb.press(VK_PERIOD), False)
    check("꺼짐: 재주입 없음", kb.vks(), [])

    # 핫키로 토글
    kb = Keyboard()
    check("기본값은 켜짐", kb.snap()["punctuation"], True)
    kb.hotkey(ime_mod.HOTKEY_PUNCT)
    check("Ctrl+Alt+P 로 꺼짐", kb.snap()["punctuation"], False)

    # ---------------------------------------------------- 순서 보장
    kb = Keyboard(punctuation=False)
    kb.type_keys("gk")
    check("기호 키 삼킴", kb.press(VK_PERIOD), True)
    check("확정분 먼저", kb.committed(), "は")
    check("기호 키 재주입", kb.vks(), [VK_PERIOD])

    kb = Keyboard()
    check("빈 상태 Space 는 통과", kb.press(VK_SPACE), False)

    # ---------------------------------------------------- 꺼진 상태는 전부 통과
    kb = Keyboard(enabled=False)
    check("꺼짐: 글자 키 통과", kb.press(ord("G")), False)
    check("꺼짐: 아무것도 안 보냄", kb.committed(), "")

    # ---------------------------------------------------- 핫키
    kb = Keyboard(enabled=False)
    kb.hotkey(ime_mod.HOTKEY_TOGGLE)
    check("Ctrl+Alt+J 로 켜짐", kb.snap()["enabled"], True)
    kb.hotkey(ime_mod.HOTKEY_KANA)
    check("Ctrl+Alt+K 로 가타카나", kb.snap()["katakana"], True)
    kb.hotkey(ime_mod.HOTKEY_QUIT)
    check("Ctrl+Alt+Q 로 종료 요청", kb.ime.quit_requested(), True)

    kb = Keyboard()
    kb.type_keys("gk")
    kb.hotkey(ime_mod.HOTKEY_KANA)
    check("모드 전환 시 확정", kb.committed(), "は")

    # ---------------------------------------------------- Ctrl 단축키는 통과
    kb = Keyboard()
    kb.type_keys("gk")
    swallowed = kb.ime.on_key(ord("C"), True, False, True, False, False)
    check("Ctrl+C 는 통과", swallowed, False)
    check("Ctrl+C 전에 확정", kb.committed(), "は")

    # ---------------------------------------------------- keyup 쌍 처리
    kb = Keyboard()
    check("keydown 삼킴",
          kb.ime.on_key(ord("G"), True, False, False, False, False), True)
    check("keyup 도 삼킴",
          kb.ime.on_key(ord("G"), False, False, False, False, False), True)
    check("두 번째 keyup 은 통과",
          kb.ime.on_key(ord("G"), False, False, False, False, False), False)

    if fails:
        print(f"FAIL  {len(fails)}건")
        for f in fails:
            print("  -", f)
        return 1
    print("PASS  controller" + ("" if has_dict else " (사전 없이)"))
    return 0


if __name__ == "__main__":
    sys.exit(run())
