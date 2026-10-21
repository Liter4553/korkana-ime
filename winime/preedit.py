# -*- coding: utf-8 -*-
"""캐럿 옆에 뜨는 미확정 입력창 + 한자 후보 목록.

TSF 기반 진짜 IME 가 아니므로 대상 앱 안에 밑줄 글자를 띄울 수 없다.
대신 캐럿 옆에 우리 창을 붙여서 같은 느낌을 낸다.

    ┌──────────────────────┐
    │ あ  가쿠세이데스      │   <- 지금 치고 있는 한글
    │     がくせいです      │   <- 변환된 미확정 읽기
    ├──────────────────────┤
    │ 1  学生です          │   <- 후보 목록 (Space 를 누른 뒤에만)
    │ 2  がくせいです       │
    └──────────────────────┘

확정된 글자만 대상 앱으로 들어가고, 위 내용은 전부 이 창에만 머문다.
"""

import ctypes
import tkinter as tk
from ctypes import wintypes

from . import winapi

# 포커스를 빼앗지 않고 작업표시줄에도 안 뜨게 하는 확장 스타일
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080

user32 = winapi.user32
user32.GetParent.restype = wintypes.HWND
user32.GetParent.argtypes = (wintypes.HWND,)
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.GetWindowLongPtrW.argtypes = (wintypes.HWND, ctypes.c_int)
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = (
    wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t)


def _make_non_activating(tk_window) -> None:
    """Tk 창이 클릭/표시 시 포커스를 훔치지 않도록 만든다."""
    try:
        hwnd = user32.GetParent(tk_window.winfo_id()) or tk_window.winfo_id()
        style = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongPtrW(
            hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
    except Exception:
        pass    # 실패해도 기능상 치명적이지 않다


# ---------------------------------------------------------------- 색
BG = "#1b1f2a"
FG = "#e8ecf4"
DIM = "#8b93a7"
SEL_BG = "#2f6fed"
SEL_FG = "#ffffff"
LINE = "#2c3242"
MODE_COLORS = {
    "hira": ("#2f6fed", "#ffffff"),   # あ
    "kata": ("#17a07a", "#ffffff"),   # ア
    "off":  ("#4a5064", "#c6cbd8"),   # A
}
MODE_TEXT = {"hira": "あ", "kata": "ア", "off": "A"}
MAX_ROWS = 9
TICK_MS = 40
CARET_GAP = 4        # 캐럿과 창 사이 간격
IDLE_MARGIN = 24     # 치고 있지 않을 때 작업 영역 모서리에서 띄울 거리


class PreeditOverlay:
    """ime 객체의 상태를 폴링해 화면에 띄운다. run() 은 블로킹."""

    def __init__(self, ime):
        self.ime = ime
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.96)
        self.root.configure(bg=BG)

        # --- 윗줄: 모드 칩 + [치고 있는 한글 / 변환된 가나] + 힌트
        top = tk.Frame(self.root, bg=BG, padx=6, pady=4)
        top.pack(fill="x")

        self.mode_label = tk.Label(
            top, text=MODE_TEXT["hira"], font=("Malgun Gothic", 11, "bold"),
            bg=MODE_COLORS["hira"][0], fg=MODE_COLORS["hira"][1],
            padx=7, pady=1,
        )
        self.mode_label.pack(side="left")

        # 입력(한글) 위, 결과(가나) 아래. 아무것도 안 치면 통째로 숨긴다.
        self.text_frame = tk.Frame(top, bg=BG)

        self.hangul_label = tk.Label(
            self.text_frame, text="", font=("Malgun Gothic", 10),
            bg=BG, fg=DIM, padx=8, anchor="w",
        )
        self.hangul_label.pack(fill="x")

        self.reading_label = tk.Label(
            self.text_frame, text="", font=("Malgun Gothic", 13),
            bg=BG, fg=FG, padx=8, anchor="w",
        )
        self.reading_label.pack(fill="x")

        self._text_shown = False

        self.hint_label = tk.Label(
            top, text="", font=("Malgun Gothic", 8), bg=BG, fg=DIM, padx=4,
        )
        self.hint_label.pack(side="right")

        # --- 아랫줄: 후보 목록 (필요할 때만 pack 한다)
        self.sep = tk.Frame(self.root, bg=LINE, height=1)
        self.cand_frame = tk.Frame(self.root, bg=BG, padx=4, pady=3)

        self.rows = []
        for _ in range(MAX_ROWS):
            row = tk.Frame(self.cand_frame, bg=BG)
            num = tk.Label(row, font=("Malgun Gothic", 9), bg=BG, fg=DIM,
                           width=2, anchor="w", padx=3)
            num.pack(side="left")
            text = tk.Label(row, font=("Malgun Gothic", 12), bg=BG, fg=FG,
                            anchor="w", padx=4)
            text.pack(side="left", fill="x")
            self.rows.append((row, num, text))

        self._cand_shown = False

        # 칩을 직접 눌러도 조작할 수 있게
        for widget in (self.root, top, self.mode_label, self.reading_label):
            widget.bind("<Button-1>", lambda e: self.ime.toggle_enabled())
            widget.bind("<Button-3>", lambda e: self.ime.request_quit())

        self.root.deiconify()
        self.root.update_idletasks()
        _make_non_activating(self.root)

        self._last = None
        self.root.after(TICK_MS, self._tick)

    # ------------------------------------------------------------ 갱신
    def _tick(self) -> None:
        if self.ime.quit_requested():
            self.root.quit()
            return

        snap = self.ime.snapshot()
        key = (snap["enabled"], snap["katakana"], snap["punctuation"],
               snap["hangul"], snap["reading"],
               tuple(snap["candidates"]), snap["index"])
        if key != self._last:
            self._render(snap)
            self._last = key

        self._reposition(composing=bool(snap["reading"]))
        self.root.after(TICK_MS, self._tick)

    def _render(self, snap: dict) -> None:
        mode = ("off" if not snap["enabled"]
                else ("kata" if snap["katakana"] else "hira"))
        bg, fg = MODE_COLORS[mode]
        self.mode_label.configure(text=MODE_TEXT[mode], bg=bg, fg=fg)

        # 구두점 치환은 눈에 안 보이는 설정이라 현재 상태를 힌트에 박아 둔다
        punct = "。" if snap["punctuation"] else "."
        self.hint_label.configure(
            text=f"Ctrl+Alt+J 끄기 · K 가나전환 · P 구두점({punct}) · Q 종료")

        hangul, reading = snap["hangul"], snap["reading"]
        self.hangul_label.configure(text=hangul)
        self.reading_label.configure(text=reading)

        # 치는 중이 아니면 두 줄을 숨겨 칩만 남긴다
        want_text = bool(hangul or reading)
        if want_text and not self._text_shown:
            self.text_frame.pack(side="left")
            self._text_shown = True
        elif not want_text and self._text_shown:
            self.text_frame.pack_forget()
            self._text_shown = False

        cands = snap["candidates"][:MAX_ROWS]
        if cands:
            for i, (row, num, text) in enumerate(self.rows):
                if i >= len(cands):
                    row.pack_forget()
                    continue
                chosen = i == snap["index"]
                rbg = SEL_BG if chosen else BG
                num.configure(text=str(i + 1), bg=rbg,
                              fg=SEL_FG if chosen else DIM)
                text.configure(text=cands[i], bg=rbg,
                               fg=SEL_FG if chosen else FG)
                row.configure(bg=rbg)
                row.pack(fill="x")
            if not self._cand_shown:
                self.sep.pack(fill="x")
                self.cand_frame.pack(fill="x")
                self._cand_shown = True
        elif self._cand_shown:
            self.cand_frame.pack_forget()
            self.sep.pack_forget()
            self._cand_shown = False

    def _reposition(self, composing: bool) -> None:
        self.root.update_idletasks()
        # winfo_width/height 는 창이 실제로 다시 그려진 뒤에야 바뀐다.
        # 후보창이 막 늘어난 틱에는 옛 크기가 나오므로 요청 크기를 쓴다.
        w = self.root.winfo_reqwidth()
        h = self.root.winfo_reqheight()

        caret = winapi.caret_rect() if composing else None
        if caret is not None:
            cx, ctop, cbottom = caret
            left, top, right, bottom = winapi.work_area_at(cx, cbottom)
            x = cx
            y = cbottom + CARET_GAP
            if y + h > bottom:
                # 아래가 모자라면 캐럿 위로 뒤집는다.
                # 위도 모자랄 때만 작업 영역 안으로 밀어 넣는다.
                above = ctop - h - CARET_GAP
                y = above if above >= top else bottom - h
        else:
            left, top, right, bottom = winapi.work_area_for_window(
                winapi.foreground_window())
            x = right - w - IDLE_MARGIN
            y = bottom - h - IDLE_MARGIN

        # 작업 영역 밖으로는 절대 나가지 않게. 공간이 모자라면 윗변을 살린다.
        x = max(left, min(x, right - w))
        y = max(top, min(y, bottom - h))
        self.root.geometry(f"+{x}+{y}")

    def run(self) -> None:
        self.root.mainloop()
        try:
            self.root.destroy()
        except Exception:
            pass
