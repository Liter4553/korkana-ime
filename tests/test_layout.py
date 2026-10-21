# -*- coding: utf-8 -*-
"""오버레이 배치 테스트 (Windows + 화면 필요).

실행: python tests/test_layout.py

후보창이 작업표시줄 뒤로 들어가 후보가 잘리던 버그의 회귀 테스트.
캐럿을 화면 여기저기에 가짜로 놓고, 창이 늘 작업 영역 안에 들어오면서
캐럿을 가리지 않는지 확인한다.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from winime import winapi

CARET_H = 24
_caret_y = [0]
_composing = [True]

# 실제 캐럿 대신 우리가 정한 위치를 쓰게 한다
winapi.caret_rect = lambda: (400, _caret_y[0], _caret_y[0] + CARET_H)

from winime.preedit import PreeditOverlay
from ime import KoreanKanaIME

user32 = winapi.user32


def run():
    screen_h = user32.GetSystemMetrics(1)
    wl, wt, wr, wb = winapi.work_area_at(user32.GetSystemMetrics(0) // 2,
                                         screen_h // 2)
    taskbar = screen_h - wb
    print(f"작업 영역 {wl},{wt}..{wr},{wb}  (화면 높이 {screen_h},"
          f" 작업표시줄 {taskbar}px)")

    ime = KoreanKanaIME(enabled=True)
    overlay = PreeditOverlay(ime)
    fails = []

    def place(caret_y, composing=True):
        _caret_y[0] = caret_y
        overlay._reposition(composing=composing)
        root = overlay.root
        root.update_idletasks()
        return (root.winfo_x(), root.winfo_y(),
                root.winfo_reqwidth(), root.winfo_reqheight())

    def check(label, caret_y, composing=True):
        x, y, w, h = place(caret_y, composing)
        if not (x >= wl and y >= wt and x + w <= wr and y + h <= wb):
            fails.append(
                f"{label}: 창 {w}x{h} +{x}+{y} 이 작업 영역 "
                f"{wl},{wt}..{wr},{wb} 밖으로 나감")
            return
        if composing:
            covers = y < caret_y + CARET_H and y + h > caret_y
            if covers:
                fails.append(f"{label}: 창이 캐럿(y={caret_y})을 가림")

    def body():
        # 후보창을 띄워 세로로 가장 긴 상태를 만든다
        with ime._lock:
            for letter in "rkzntpdl":              # 가쿠세이
                ime.comp.feed_key(letter)
            ime.comp.start_selection()
        snap = ime.snapshot()
        overlay._render(snap)
        overlay.root.update_idletasks()     # 이게 없으면 옛 크기가 나온다
        n = len(snap["candidates"])
        h = overlay.root.winfo_reqheight()
        print(f"후보 {n}개, 창 높이 {h}px")
        if n < 2:
            print("  (사전이 없어 후보가 짧다 - 그래도 배치 규칙은 검사한다)")
        elif h < 100:
            # 창이 작으면 어디에 놔도 들어가서 이 테스트가 아무것도 검증하지 못한다
            fails.append(f"후보 {n}개인데 창 높이가 {h}px - 후보창이 안 펼쳐졌다")

        # 화면 위에서 아래까지 훑는다. 아래쪽은 반드시 위로 뒤집혀야 한다.
        for caret_y in range(wt, wb, 37):
            check(f"캐럿 y={caret_y}", caret_y)
        for caret_y in (wb - 5, wb - 1, wb, wb + 50):   # 경계/화면 밖
            check(f"캐럿 y={caret_y} (경계)", caret_y)

        # 대기 상태 칩도 작업 영역 안이어야 한다
        with ime._lock:
            ime.comp.clear()
        overlay._render(ime.snapshot())
        check("대기 칩", 0, composing=False)

        # 아래 공간이 모자라면 실제로 뒤집었는지 확인
        with ime._lock:
            for letter in "rkzntpdl":
                ime.comp.feed_key(letter)
            ime.comp.start_selection()
        overlay._render(ime.snapshot())
        overlay.root.update_idletasks()
        x, y, w, h = place(wb - 60)
        if h < 100:
            fails.append(f"뒤집기 검사용 창이 너무 작다 ({h}px)")
        if y + h > wb - 60:
            fails.append(f"아래 공간이 없는데 위로 뒤집지 않음: +{x}+{y} 높이 {h}")

        ime.request_quit()

    overlay.root.after(300, body)
    overlay.run()

    if fails:
        print(f"FAIL  {len(fails)}건")
        for f in fails[:10]:
            print("  -", f)
        return 1
    print("PASS  layout")
    return 0


if __name__ == "__main__":
    sys.exit(run())
