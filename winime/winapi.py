# -*- coding: utf-8 -*-
"""전역 키보드 훅 / 유니코드 입력 / 캐럿 위치 -- ctypes 바인딩.

외부 패키지(keyboard, pynput 등) 없이 Win32 API 를 직접 쓴다.
"""

import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
ULONG_PTR = wintypes.WPARAM

# ---------------------------------------------------------------- 상수
WH_KEYBOARD_LL = 13
HC_ACTION = 0
WM_KEYDOWN, WM_KEYUP = 0x0100, 0x0101
WM_SYSKEYDOWN, WM_SYSKEYUP = 0x0104, 0x0105
WM_QUIT = 0x0012

LLKHF_INJECTED = 0x10

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

# 우리가 SendInput 으로 넣은 이벤트를 훅에서 다시 잡지 않도록 하는 표식
INJECT_MARK = 0x4B4F524B

VK_BACK, VK_TAB, VK_RETURN = 0x08, 0x09, 0x0D
VK_SHIFT, VK_CONTROL, VK_MENU = 0x10, 0x11, 0x12
VK_ESCAPE, VK_SPACE = 0x1B, 0x20
VK_LWIN, VK_RWIN = 0x5B, 0x5C
VK_OEM_MINUS = 0xBD
VK_A, VK_Z = 0x41, 0x5A


# ---------------------------------------------------------------- 구조체
class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG), ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),      # 작업표시줄을 뺀 영역
        ("dwFlags", wintypes.DWORD),
    ]


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND), ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND), ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND), ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]


# ---------------------------------------------------------------- 함수 시그니처
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.SetWindowsHookExW.argtypes = (
    ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD)
user32.CallNextHookEx.restype = LRESULT
user32.CallNextHookEx.argtypes = (
    wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.UnhookWindowsHookEx.argtypes = (wintypes.HHOOK,)

user32.SendInput.restype = wintypes.UINT
user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)

user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)

user32.GetMessageW.restype = wintypes.BOOL
user32.GetMessageW.argtypes = (
    ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT)

user32.PostThreadMessageW.restype = wintypes.BOOL
user32.PostThreadMessageW.argtypes = (
    wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

user32.GetGUIThreadInfo.restype = wintypes.BOOL
user32.GetGUIThreadInfo.argtypes = (wintypes.DWORD, ctypes.POINTER(GUITHREADINFO))

user32.ClientToScreen.restype = wintypes.BOOL
user32.ClientToScreen.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.POINT))

user32.GetForegroundWindow.restype = wintypes.HWND

user32.MonitorFromPoint.restype = ctypes.c_void_p
user32.MonitorFromPoint.argtypes = (wintypes.POINT, wintypes.DWORD)
user32.MonitorFromWindow.restype = ctypes.c_void_p
user32.MonitorFromWindow.argtypes = (wintypes.HWND, wintypes.DWORD)
user32.GetMonitorInfoW.restype = wintypes.BOOL
user32.GetMonitorInfoW.argtypes = (ctypes.c_void_p, ctypes.POINTER(MONITORINFO))

kernel32.GetCurrentThreadId.restype = wintypes.DWORD

MONITOR_DEFAULTTONEAREST = 2


# ---------------------------------------------------------------- 입력 보내기
def _unicode_event(ch: str, keyup: bool) -> INPUT:
    flags = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if keyup else 0)
    inp = INPUT(type=INPUT_KEYBOARD)
    inp.ki = KEYBDINPUT(wVk=0, wScan=ord(ch), dwFlags=flags,
                        time=0, dwExtraInfo=INJECT_MARK)
    return inp


def send_text(text: str) -> None:
    """유니코드 문자열을 현재 포커스된 창에 입력한다."""
    if not text:
        return
    events = []
    for ch in text:
        events.append(_unicode_event(ch, False))
        events.append(_unicode_event(ch, True))
    arr = (INPUT * len(events))(*events)
    user32.SendInput(len(events), arr, ctypes.sizeof(INPUT))


def send_vk(vk: int) -> None:
    """가상 키 하나를 눌렀다 뗀다."""
    events = []
    for keyup in (False, True):
        inp = INPUT(type=INPUT_KEYBOARD)
        inp.ki = KEYBDINPUT(wVk=vk, wScan=0,
                            dwFlags=KEYEVENTF_KEYUP if keyup else 0,
                            time=0, dwExtraInfo=INJECT_MARK)
        events.append(inp)
    arr = (INPUT * len(events))(*events)
    user32.SendInput(len(events), arr, ctypes.sizeof(INPUT))


# ---------------------------------------------------------------- 키 상태
def is_down(vk: int) -> bool:
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def modifiers():
    """(shift, ctrl, alt, win) 눌림 상태."""
    return (
        is_down(VK_SHIFT),
        is_down(VK_CONTROL),
        is_down(VK_MENU),
        is_down(VK_LWIN) or is_down(VK_RWIN),
    )


# ---------------------------------------------------------------- 캐럿 위치
def caret_rect():
    """포커스된 창의 캐럿 위치를 (x, 윗변, 아랫변) 화면 좌표로.

    아랫변만으로는 캐럿 아래에 창을 붙일 수만 있다. 아래 공간이 모자라
    위로 뒤집을 때 글자 줄을 가리지 않으려면 윗변도 있어야 한다.
    알아낼 수 없으면 None.
    """
    gti = GUITHREADINFO()
    gti.cbSize = ctypes.sizeof(GUITHREADINFO)
    if not user32.GetGUIThreadInfo(0, ctypes.byref(gti)):
        return None
    if not gti.hwndCaret:
        return None
    rc = gti.rcCaret
    if rc.right == rc.left and rc.bottom == rc.top:
        return None
    top = wintypes.POINT(rc.left, rc.top)
    bottom = wintypes.POINT(rc.left, rc.bottom)
    if not user32.ClientToScreen(gti.hwndCaret, ctypes.byref(top)):
        return None
    if not user32.ClientToScreen(gti.hwndCaret, ctypes.byref(bottom)):
        return None
    if bottom.x <= 0 and bottom.y <= 0:
        return None
    return bottom.x, top.y, bottom.y


def foreground_window() -> int:
    return user32.GetForegroundWindow() or 0


# ---------------------------------------------------------------- 모니터
def _work_area(hmonitor):
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    if not hmonitor or not user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
        # 못 가져오면 주 화면 전체로 (작업표시줄을 덮을 수는 있어도 사라지진 않는다)
        return 0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    rc = info.rcWork
    return rc.left, rc.top, rc.right, rc.bottom


def work_area_at(x: int, y: int):
    """(x, y) 가 속한 모니터의 작업 영역 (left, top, right, bottom).

    화면 전체가 아니라 **작업 영역**이어야 한다. 전체 높이로 맞추면 창
    아래끝이 작업표시줄 뒤로 들어가 후보가 가려진다.
    """
    hmon = user32.MonitorFromPoint(wintypes.POINT(x, y), MONITOR_DEFAULTTONEAREST)
    return _work_area(hmon)


def work_area_for_window(hwnd: int):
    """창이 올라가 있는 모니터의 작업 영역."""
    hmon = user32.MonitorFromWindow(wintypes.HWND(hwnd) if hwnd else None,
                                    MONITOR_DEFAULTTONEAREST)
    return _work_area(hmon)


# ---------------------------------------------------------------- 훅
class KeyboardHook:
    """저수준 키보드 훅. 전용 스레드에서 run() 을 돌려야 한다.

    callback(vk, is_keydown, shift, ctrl, alt, win) -> True 면 그 키를 삼킨다.
    """

    def __init__(self, callback):
        self._callback = callback
        self._hook = None
        self._thread_id = 0
        # GC 되면 즉시 크래시하므로 반드시 레퍼런스를 들고 있어야 한다
        self._proc = HOOKPROC(self._dispatch)

    def _dispatch(self, nCode, wParam, lParam):
        if nCode != HC_ACTION:
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents

        # 우리가 넣은 입력이거나 다른 프로그램이 주입한 입력은 건드리지 않는다
        if kb.dwExtraInfo == INJECT_MARK or (kb.flags & LLKHF_INJECTED):
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        down = wParam in (WM_KEYDOWN, WM_SYSKEYDOWN)
        up = wParam in (WM_KEYUP, WM_SYSKEYUP)
        if down or up:
            try:
                if self._callback(kb.vkCode, down, *modifiers()):
                    return 1                      # 삼킴
            except Exception:
                # 훅은 절대 죽지 않게 한다. 콘솔이 없을 수도 있어 파일로 남긴다.
                import applog
                applog.exception("훅 콜백")

        return user32.CallNextHookEx(None, nCode, wParam, lParam)

    def run(self) -> None:
        """훅을 걸고 메시지 루프를 돈다 (stop() 까지 블로킹)."""
        self._thread_id = kernel32.GetCurrentThreadId()
        self._hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc, None, 0)
        if not self._hook:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            msg = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                pass
        finally:
            user32.UnhookWindowsHookEx(self._hook)
            self._hook = None

    def stop(self) -> None:
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
