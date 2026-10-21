# -*- coding: utf-8 -*-
"""실제 훅 + 오버레이 스모크 테스트 (Windows + 화면 필요).

실행: python tests/smoke_overlay.py

test_ime.py 는 훅을 가짜로 두고 키 처리만 본다. 이 파일은 반대로,
**진짜 키보드 훅을 걸고 진짜 Tk 창을 띄워서** 그 둘이 크래시 없이
서는지 확인한다. 자동으로 상태를 만들어 보고 몇 초 뒤 혼자 끝난다.

확인하는 것
  - SetWindowsHookExW 가 성공하는가 (보안 프로그램이 막지 않는가)
  - 네 가지 표시 상태가 제대로 그려지는가
  - 후보창이 펼쳐지고 접히면서 창 크기가 따라오는가
  - 훅과 Tk 가 깨끗하게 종료되는가

주의: IME 를 켠 상태로 두지 않으므로 타자를 가로채지 않는다.
실제 물리 타자가 대상 앱에 들어가는지는 이걸로 확인할 수 없다
(우리가 보내는 키는 주입 플래그가 붙어 훅이 의도적으로 무시한다).
"""

import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from winime import winapi
from winime.preedit import PreeditOverlay
from korkana import kanji
from ime import KoreanKanaIME

# 가쿠세이 (두벌식)
SAMPLE = "rkzntpdl"


def run():
    print(f"사전: {kanji.dict_info()}")

    ime = KoreanKanaIME(enabled=False)
    hook = winapi.KeyboardHook(ime.on_key)
    hook_error = []

    def hook_thread():
        try:
            hook.run()
        except OSError as exc:
            hook_error.append(exc)

    threading.Thread(target=hook_thread, daemon=True).start()
    time.sleep(0.6)

    if hook_error or hook._hook is None:
        print(f"FAIL  훅을 걸지 못했다: {hook_error[0] if hook_error else '원인 불명'}")
        print("      보안 프로그램이 막고 있을 수 있다.")
        return 1
    print("훅 설치: OK")

    overlay = PreeditOverlay(ime)
    fails = []

    def shown():
        overlay.root.update_idletasks()
        return (overlay.hangul_label.cget("text"),
                overlay.reading_label.cget("text"),
                overlay.root.winfo_reqwidth(),
                overlay.root.winfo_reqheight())

    def step_consonant():
        with ime._lock:
            ime.enabled = True
            ime.comp.feed_key("w")                 # ㅈ - 모음이 아직 없다
        overlay._render(ime.snapshot())
        hangul, reading, _, _ = shown()
        print(f"  자음만      한글={hangul!r}  가나={reading!r}")
        if hangul != "ㅈ":
            fails.append(f"자음만: 한글 줄이 {hangul!r}")
        if reading != "":
            fails.append(f"자음만: 가나 줄에 {reading!r} 가 보인다 (비어야 함)")

    def step_phrase():
        with ime._lock:
            ime.comp.clear()
            for letter in SAMPLE:
                ime.comp.feed_key(letter)
        overlay._render(ime.snapshot())
        hangul, reading, _, _ = shown()
        print(f"  문구        한글={hangul!r}  가나={reading!r}")
        if not hangul or not reading:
            fails.append("문구: 두 줄 중 하나가 비었다")

    def step_candidates():
        with ime._lock:
            ime.comp.start_selection()
        snap = ime.snapshot()
        overlay._render(snap)
        _, _, _, height = shown()
        print(f"  후보 {len(snap['candidates'])}개  창 높이={height}px")
        print(f"    {snap['candidates'][:3]}")
        if kanji.available() and len(snap["candidates"]) < 2:
            fails.append("후보: 사전이 있는데 후보가 1개 이하")
        if len(snap["candidates"]) >= 2 and height < 100:
            fails.append(f"후보: 창이 안 펼쳐졌다 ({height}px)")

    def step_empty():
        with ime._lock:
            ime.comp.clear()
            ime.enabled = False
        overlay._render(ime.snapshot())
        hangul, reading, _, height = shown()
        print(f"  빈 상태     한글={hangul!r}  가나={reading!r}  창 높이={height}px")
        if hangul or reading:
            fails.append("빈 상태: 두 줄이 안 지워졌다")
        if height > 60:
            fails.append(f"빈 상태: 창이 안 접혔다 ({height}px)")
        ime.request_quit()

    for i, step in enumerate((step_consonant, step_phrase,
                              step_candidates, step_empty)):
        overlay.root.after(500 + i * 450, step)

    overlay.run()
    hook.stop()

    if fails:
        print(f"FAIL  {len(fails)}건")
        for f in fails:
            print("  -", f)
        return 1
    print("PASS  smoke (훅 설치 · 네 가지 표시 상태 · 정상 종료)")
    return 0


if __name__ == "__main__":
    sys.exit(run())
