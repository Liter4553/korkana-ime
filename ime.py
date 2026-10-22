# -*- coding: utf-8 -*-
"""한국어 발음으로 일본어를 치는 IME (한자 변환 포함).

    실행:  python ime.py
    변환만: python ime.py --convert 하지메마시떼
    대화형: python ime.py --repl

동작 방식
---------
Windows는 저수준 키보드 훅으로 영문 자리 키를 가로채서
  두벌식 낱자 -> 한글 음절 -> 히라가나 읽기 -> (Space) 한자 후보 -> 확정
한다. 윈도우 한국어 IME 를 켤 필요가 없다(영문 상태에서 쓰는 걸 권장).

확정된 글자만 대상 앱으로 들어간다. 미확정 읽기와 후보 목록은 캐럿 옆에
뜨는 우리 창에만 있다. TSF 기반 IME 가 아니라 앱 안에 밑줄 글자를 넣을 수
없기 때문이다.

Linux는 IBus 엔진을 실행한다. macOS는 설치된 InputMethodKit 앱을 사용한다.
세 플랫폼에서 --convert / --repl은 OS 입력기와 독립적으로 사용할 수 있다.
"""

import argparse
import sys
import threading

import applog
from korkana import kanji
from korkana.kana import convert
from korkana.tables import to_katakana

# Re-export the established Windows interface for callers and the overlay.
from korkana.controller import (  # noqa: F401
    KoreanKanaIME as _Controller, HOTKEY_TOGGLE, HOTKEY_KANA,
    HOTKEY_QUIT, HOTKEY_PUNCT, PUNCTUATION, MODIFIER_VKS, _is_text_key,
)


class KoreanKanaIME(_Controller):
    def __init__(self, enabled=False, katakana=False, punctuation=True):
        # CLI conversion and non-Windows imports never load user32.dll.
        from winime import winapi
        super().__init__(enabled, katakana, punctuation,
                         send_text=winapi.send_text, send_key=winapi.send_vk)


# ---------------------------------------------------------------- 실행 모드
BANNER = """\
  한국어 발음 -> 일본어 IME
  ----------------------------------------------------------
  지금은 꺼져 있습니다.  Ctrl+Alt+J 로 켜세요.
  켠 뒤 영문 입력 상태에서 그냥 치면 됩니다.

      와타시하가쿠세이데스  ->  Space  ->  私は学生です
      (치면 캐럿 옆 창에 읽기가 쌓이고, Space 로 한자 후보)

  Space        한자 변환 / 다음 후보
  1~9          후보 번호로 바로 확정
  위아래 화살표  후보 이동
  Enter        변환 없이 가나로 확정
  Esc          후보창 닫기 (한 번 더 누르면 입력 취소)
  -  (하이픈)  장음 부호 ー

  Ctrl+Alt+J   IME 켜기/끄기
  Ctrl+Alt+K   히라가나 <-> 가타카나 (가타카나는 한자 변환 없음)
  Ctrl+Alt+Q   종료
  ----------------------------------------------------------
  화면 우하단 칩: 클릭=켜기/끄기, 우클릭=종료
"""


def run_ime(enabled: bool = False) -> int:
    from winime import winapi
    from winime.preedit import PreeditOverlay

    ime = KoreanKanaIME(enabled=enabled)
    hook = winapi.KeyboardHook(ime.on_key)

    error = []

    def hook_thread():
        try:
            hook.run()
        except OSError as exc:
            error.append(exc)
            ime.request_quit()

    thread = threading.Thread(target=hook_thread, daemon=True)
    thread.start()

    applog.log(BANNER)
    applog.log(f"  사전: {kanji.dict_info()}")
    applog.log(f"  로그: {applog.log_path()}\n")

    overlay = PreeditOverlay(ime)
    try:
        overlay.run()
    except KeyboardInterrupt:
        pass
    finally:
        hook.stop()

    if error:
        applog.log(f"[오류] 키보드 훅을 걸 수 없습니다: {error[0]}")
        applog.log("      보안 프로그램이 막고 있거나, 관리자 권한이 필요할 수 있습니다.")
        return 1
    applog.log("[종료]")
    return 0


def run_repl() -> int:
    katakana = False
    print(f"사전: {kanji.dict_info()}")
    print("한글 발음을 입력하면 가나와 한자 후보를 보여 줍니다."
          " (:k 가나전환, 빈 줄 종료)")
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            break
        if line == ":k":
            katakana = not katakana
            print(f"  모드: {'가타카나' if katakana else '히라가나'}")
            continue

        reading = convert(line)
        if katakana:
            print("  " + to_katakana(reading))
            continue
        print("  읽기: " + reading)
        for i, cand in enumerate(kanji.candidates(reading), 1):
            print(f"    {i}. {cand}")
    return 0


def main(argv=None) -> int:
    applog.setup_console()

    parser = argparse.ArgumentParser(
        description="한국어 발음으로 일본어를 치는 전역 IME")
    parser.add_argument("--convert", metavar="한글",
                        help="문자열 하나만 변환하고 끝낸다")
    parser.add_argument("--repl", action="store_true",
                        help="대화형으로 변환만 해 본다")
    parser.add_argument("--katakana", action="store_true",
                        help="--convert 를 가타카나로")
    parser.add_argument("--kanji", action="store_true",
                        help="--convert 결과의 한자 후보도 보여준다")
    parser.add_argument("--on", action="store_true",
                        help="IME 를 켜진 상태로 시작한다")
    args = parser.parse_args(argv)

    if args.convert is not None:
        reading = convert(args.convert, args.katakana)
        print(reading)
        if args.kanji and not args.katakana:
            for i, cand in enumerate(kanji.candidates(reading), 1):
                print(f"  {i}. {cand}")
        return 0
    if args.repl:
        return run_repl()
    if sys.platform == "linux":
        from linuxime.engine import main as run_linux
        return run_linux([])
    if sys.platform == "darwin":
        parser.error("macOS에서는 설치한 KorKanaIME 입력 소스를 선택하세요. "
                     "설치 방법: docs/PORTING.md")
    if sys.platform != "win32":
        parser.error(f"지원하지 않는 플랫폼: {sys.platform}")
    return run_ime(enabled=args.on)


if __name__ == "__main__":
    sys.exit(main())
