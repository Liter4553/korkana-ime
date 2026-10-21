# -*- coding: utf-8 -*-
"""KorKanaIME 설치 프로그램.

빌드하면 KorKanaIME-Setup.exe 하나가 나온다. 그 안에 앱 전체(payload.zip)가
들어 있어서 인터넷 없이 설치된다.

사용자 폴더(%LOCALAPPDATA%)에 깔기 때문에 관리자 권한이 필요 없다.
Program Files 에 깔면 UAC 를 띄워야 하는데, 키보드 훅을 거는 프로그램이
관리자 권한까지 요구하면 보안 경고만 더 늘어난다.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import tkinter as tk
import winreg
import zipfile
from tkinter import messagebox

APP_NAME = "KorKanaIME"
DISPLAY_NAME = "한국어 발음 일본어 IME"
VERSION = "1.0.0"
EXE_NAME = "KorKanaIME.exe"
PAYLOAD = "payload.zip"
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\KorKanaIME"


# ---------------------------------------------------------------- 경로
def say(text: str) -> None:
    """콘솔이 있으면 콘솔에, 없으면 로그 파일에만.

    설치 프로그램은 console=False 로 빌드되므로 무인 모드에서도
    sys.stdout 이 None 이다. 그대로 print 하면 그 자리에서 죽는다.
    """
    out = sys.stdout
    if out is not None:
        try:
            out.write(text + "\n")
            out.flush()
        except Exception:
            pass
    try:
        log = os.path.join(tempfile.gettempdir(), "KorKanaIME-setup.log")
        with open(log, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except Exception:
        pass


def resource(name: str) -> str:
    """번들 안의 파일 경로 (PyInstaller 는 _MEIPASS 에 풀어 둔다)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def default_target() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "Programs", APP_NAME)


def start_menu_dir() -> str:
    return os.path.join(os.environ.get("APPDATA", ""),
                        "Microsoft", "Windows", "Start Menu", "Programs")


def startup_dir() -> str:
    return os.path.join(start_menu_dir(), "Startup")


# ---------------------------------------------------------------- 바로가기
def make_shortcut(link_path: str, target: str, workdir: str, icon: str) -> None:
    """PowerShell 의 WScript.Shell 로 .lnk 를 만든다.

    pywin32 를 끌어오지 않으려고 이렇게 한다. 설치 프로그램 하나 때문에
    의존성을 늘릴 이유가 없다.
    """
    script = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut("
        f"'{link_path}'); "
        f"$s.TargetPath = '{target}'; "
        f"$s.WorkingDirectory = '{workdir}'; "
        f"$s.IconLocation = '{icon}'; "
        f"$s.Description = '{DISPLAY_NAME}'; "
        "$s.Save()"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive",
         "-ExecutionPolicy", "Bypass", "-Command", script],
        check=True, capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW)


# ---------------------------------------------------------------- 설치
def write_uninstaller(target: str) -> str:
    """제거용 배치 파일을 만들고 경로를 돌려준다.

    자기 자신이 깔린 폴더를 지워야 해서, 임시 폴더로 복사한 뒤 거기서 지운다.
    """
    path = os.path.join(target, "uninstall.bat")
    body = f"""@echo off
chcp 65001 >nul
echo {DISPLAY_NAME} 를 제거합니다...
taskkill /F /IM {EXE_NAME} >nul 2>&1
timeout /t 1 /nobreak >nul

del "{os.path.join(start_menu_dir(), APP_NAME + '.lnk')}" >nul 2>&1
del "{os.path.join(startup_dir(), APP_NAME + '.lnk')}" >nul 2>&1
reg delete "HKCU\\{UNINSTALL_KEY}" /f >nul 2>&1

rem 자기가 들어 있는 폴더를 지워야 하므로 임시 폴더에서 실행한다.
rem pause 를 쓰면 창이 닫히지 않고 남아 자기 자신도 못 지운다 - timeout 으로.
set "TMPBAT=%TEMP%\\korkana_rm.bat"
> "%TMPBAT%" echo @echo off
>>"%TMPBAT%" echo timeout /t 1 /nobreak ^>nul
>>"%TMPBAT%" echo rmdir /s /q "{target}"
>>"%TMPBAT%" echo echo {DISPLAY_NAME} 를 제거했습니다.
>>"%TMPBAT%" echo timeout /t 3 /nobreak ^>nul
>>"%TMPBAT%" echo del "%%~f0"
start "" /min cmd /c "%TMPBAT%"
exit
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)
    return path


def register_uninstall(target: str, uninstaller: str) -> None:
    """제어판 > 프로그램 추가/제거 에 뜨게 한다."""
    size_kb = sum(
        os.path.getsize(os.path.join(root, name))
        for root, _, names in os.walk(target) for name in names) // 1024
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as key:
        for name, value in (
            ("DisplayName", DISPLAY_NAME),
            ("DisplayVersion", VERSION),
            ("Publisher", "korkana"),
            ("InstallLocation", target),
            ("DisplayIcon", os.path.join(target, EXE_NAME)),
            ("UninstallString", f'"{uninstaller}"'),
        ):
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD, size_kb)
        winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)


def install(target: str, autostart: bool, progress) -> str:
    """payload.zip 을 풀고 바로가기·제거 정보를 만든다. exe 경로를 돌려준다."""
    payload = resource(PAYLOAD)
    if not os.path.exists(payload):
        raise FileNotFoundError(f"설치 파일이 손상되었습니다: {PAYLOAD} 없음")

    # 기존 설치본 정리 (업데이트 설치)
    if os.path.isdir(target):
        progress("기존 설치본 정리 중...")
        subprocess.run(["taskkill", "/F", "/IM", EXE_NAME],
                       capture_output=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)
        shutil.rmtree(target, ignore_errors=True)

    progress("파일 푸는 중...")
    os.makedirs(target, exist_ok=True)
    with zipfile.ZipFile(payload) as zf:
        names = zf.namelist()
        for i, name in enumerate(names):
            zf.extract(name, target)
            if i % 40 == 0:
                progress(f"파일 푸는 중...  {i + 1}/{len(names)}")

    exe = os.path.join(target, EXE_NAME)
    if not os.path.exists(exe):
        raise FileNotFoundError(f"{EXE_NAME} 이 풀리지 않았습니다")

    progress("바로가기 만드는 중...")
    os.makedirs(start_menu_dir(), exist_ok=True)
    make_shortcut(os.path.join(start_menu_dir(), APP_NAME + ".lnk"),
                  exe, target, exe)
    startup_link = os.path.join(startup_dir(), APP_NAME + ".lnk")
    if autostart:
        os.makedirs(startup_dir(), exist_ok=True)
        make_shortcut(startup_link, exe, target, exe)
    elif os.path.exists(startup_link):
        os.remove(startup_link)

    progress("마무리 중...")
    register_uninstall(target, write_uninstaller(target))
    return exe


# ---------------------------------------------------------------- 화면
BG = "#1b1f2a"
FG = "#e8ecf4"
DIM = "#8b93a7"
ACCENT = "#2f6fed"


class SetupWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{DISPLAY_NAME} 설치")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        try:
            self.root.iconbitmap(resource("icon.ico"))
        except Exception:
            pass

        pad = tk.Frame(self.root, bg=BG, padx=28, pady=22)
        pad.pack()

        tk.Label(pad, text=DISPLAY_NAME, font=("Malgun Gothic", 15, "bold"),
                 bg=BG, fg=FG).pack(anchor="w")
        tk.Label(pad, text="한글 발음대로 치면 일본어로 바꿔 주는 입력기",
                 font=("Malgun Gothic", 9), bg=BG, fg=DIM).pack(anchor="w",
                                                                pady=(2, 16))

        tk.Label(pad, text="설치 위치", font=("Malgun Gothic", 9),
                 bg=BG, fg=DIM).pack(anchor="w")
        self.path_var = tk.StringVar(value=default_target())
        entry = tk.Entry(pad, textvariable=self.path_var, width=52,
                         font=("Malgun Gothic", 9), bg="#262b38", fg=FG,
                         relief="flat", insertbackground=FG)
        entry.pack(anchor="w", ipady=5, pady=(3, 14))

        self.autostart = tk.BooleanVar(value=False)
        tk.Checkbutton(
            pad, text="윈도우 시작할 때 자동 실행", variable=self.autostart,
            font=("Malgun Gothic", 9), bg=BG, fg=FG, selectcolor="#262b38",
            activebackground=BG, activeforeground=FG, relief="flat",
            highlightthickness=0,
        ).pack(anchor="w")

        tk.Label(
            pad,
            text=("설치 후 Ctrl+Alt+J 로 켜고 끕니다.\n"
                  "관리자 권한은 필요 없습니다 (사용자 폴더에 설치)."),
            font=("Malgun Gothic", 8), bg=BG, fg=DIM, justify="left",
        ).pack(anchor="w", pady=(10, 14))

        self.status = tk.Label(pad, text="", font=("Malgun Gothic", 9),
                               bg=BG, fg=DIM, anchor="w", width=46)
        self.status.pack(anchor="w", pady=(0, 10))

        buttons = tk.Frame(pad, bg=BG)
        buttons.pack(anchor="e")
        self.cancel_btn = tk.Button(
            buttons, text="닫기", command=self.root.destroy, width=10,
            font=("Malgun Gothic", 9), bg="#333a4a", fg=FG, relief="flat",
            activebackground="#3d4557", activeforeground=FG)
        self.cancel_btn.pack(side="left", padx=(0, 8))
        self.install_btn = tk.Button(
            buttons, text="설치", command=self.start, width=12,
            font=("Malgun Gothic", 9, "bold"), bg=ACCENT, fg="#ffffff",
            relief="flat", activebackground="#4580f5", activeforeground="#fff")
        self.install_btn.pack(side="left")

        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"+{(sw - w) // 2}+{(sh - h) // 3}")

    # ------------------------------------------------------------
    def progress(self, text: str) -> None:
        self.status.configure(text=text)
        self.root.update_idletasks()

    def start(self) -> None:
        target = self.path_var.get().strip()
        if not target:
            messagebox.showerror("설치", "설치 위치를 입력하세요.")
            return
        self.install_btn.configure(state="disabled")
        self.cancel_btn.configure(state="disabled")
        try:
            exe = install(target, self.autostart.get(), self.progress)
        except Exception as exc:
            self.progress("")
            messagebox.showerror("설치 실패", str(exc))
            self.install_btn.configure(state="normal")
            self.cancel_btn.configure(state="normal")
            return

        self.progress("설치가 끝났습니다.")
        if messagebox.askyesno(
                "설치 완료",
                f"{DISPLAY_NAME} 를 설치했습니다.\n\n지금 실행할까요?\n"
                "(실행한 뒤 Ctrl+Alt+J 로 켜세요)"):
            subprocess.Popen([exe], cwd=os.path.dirname(exe))
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


USAGE = """KorKanaIME 설치 프로그램

  KorKanaIME-Setup.exe                그냥 실행하면 설치 창이 뜬다
  KorKanaIME-Setup.exe /S             창 없이 바로 설치 (무인 설치)
  KorKanaIME-Setup.exe /S --dir 경로   설치 위치 지정
  KorKanaIME-Setup.exe /S --autostart 윈도우 시작 시 자동 실행까지 등록
"""


def silent_install(argv) -> int:
    """창 없이 설치한다. 배포·테스트용."""
    target = default_target()
    autostart = "--autostart" in argv
    if "--dir" in argv:
        index = argv.index("--dir")
        if index + 1 >= len(argv):
            say("--dir 뒤에 경로가 필요합니다.")
            return 2
        target = argv[index + 1]

    try:
        exe = install(target, autostart, say)
    except Exception as exc:
        say(f"설치 실패: {exc}")
        return 1
    say(f"설치 완료: {exe}")
    return 0


def main() -> int:
    if sys.platform != "win32":
        say("윈도우 전용입니다.")
        return 1

    argv = sys.argv[1:]
    if "--help" in argv or "/?" in argv:
        say(USAGE)
        return 0
    if "/S" in argv or "--silent" in argv:
        return silent_install(argv)

    SetupWindow().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
