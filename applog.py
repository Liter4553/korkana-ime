# -*- coding: utf-8 -*-
"""로그 출력.

콘솔 없이(--windowed) 빌드한 exe 에서는 sys.stdout 이 None 이라
print() 가 그대로 예외를 던진다. 특히 키보드 훅 콜백 안에서 터지면
훅이 통째로 죽으므로, 출력은 전부 여기를 거친다.

파일로도 남긴다. exe 로 돌릴 때는 콘솔이 없어서 그게 유일한 단서다.
"""

import os
import sys
import time

_log_file = None
_failed = False


def log_path() -> str:
    """로그 파일 위치. exe 면 LOCALAPPDATA, 소스면 프로젝트 폴더."""
    if getattr(sys, "frozen", False):
        base = os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
            "KorKanaIME")
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "ime.log")


def _open():
    global _log_file, _failed
    if _log_file is not None or _failed:
        return _log_file
    try:
        path = log_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # 매 실행마다 새로 쓴다. 오래 돌아도 파일이 무한정 커지지 않게.
        _log_file = open(path, "w", encoding="utf-8", buffering=1)
    except Exception:
        _failed = True          # 로그를 못 써도 프로그램은 계속 돌아야 한다
    return _log_file


def log(*parts) -> None:
    """한 줄 기록. 콘솔이 있으면 콘솔에도."""
    msg = " ".join(str(p) for p in parts)
    stamped = f"{time.strftime('%H:%M:%S')}  {msg}"

    handle = _open()
    if handle is not None:
        try:
            handle.write(stamped + "\n")
        except Exception:
            pass

    out = sys.stdout
    if out is not None:
        try:
            out.write(msg + "\n")
            out.flush()
        except Exception:
            pass


def exception(label: str = "예외") -> None:
    """현재 예외를 기록한다. 훅 콜백처럼 죽으면 안 되는 자리에서 쓴다."""
    import traceback
    log(f"[{label}]\n" + traceback.format_exc())


def setup_console() -> None:
    """윈도우 콘솔 기본 인코딩(cp949)으로는 가나를 못 찍는다.

    파이프로 들어온 UTF-8 한글도 못 읽으므로 stdin 까지 바꾼다.
    """
    for stream, kwargs in (
        (sys.stdout, {"errors": "replace"}),
        (sys.stderr, {"errors": "replace"}),
        (sys.stdin, {}),
    ):
        if stream is None:
            continue
        try:
            stream.reconfigure(encoding="utf-8", **kwargs)
        except Exception:
            pass
