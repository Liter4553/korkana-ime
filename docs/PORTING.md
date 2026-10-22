# Linux / macOS 포팅

현재 상태: **실험적 구현**. 공통 키 처리, Linux IBus 어댑터, macOS
InputMethodKit 어댑터와 빌드 경로를 추가했다. Windows에서 변환·공통 상태
기계·키 매핑·설치 파일 생성을 검증했다. 추가로 macOS 15.7.5 Apple Silicon에서
Mozc 포함 `.app` 빌드·설치와 TextEdit의 가나 입력·한자 변환·확정을 확인했다.
Linux 실기기, Intel Mac, 재로그인 후 자동 시작과 다른 앱의 호환성은 미검증이다.
정식 지원이나 검증된 배포판으로 취급하지 않는다.

| 플랫폼 | 연결 방식 | 검증 범위 |
|---|---|---|
| Windows | 기존 Win32 훅 + tkinter 오버레이 | 기존 키 처리 회귀 테스트 통과 |
| Linux | IBus 엔진 + 네이티브 preedit/후보창 | 공통 로직·설치 생성 테스트, 실기기 검증 필요 |
| macOS | InputMethodKit + PyObjC + py2app | Apple Silicon 빌드·설치·TextEdit 가나/한자 입력 확인, 나머지 환경 검증 필요 |

## 공통 구조

- `korkana/controller.py`: 기존 Windows 키 처리 상태 기계. 출력 함수를 주입받는다.
- `korkana/keys.py`: 플랫폼에 독립적인 내부 키 ID. Windows와의 호환을 위해 VK 값을 유지한다.
- `korkana/native.py`: OS 입력 컨텍스트 하나의 세션. 확정 문자열을 순서대로 모은다.
- `ime.py`: Windows 어댑터와 공통 CLI. 변환 CLI는 Windows DLL을 로드하지 않는다.
- `linuxime/engine.py`: IBus 키 이벤트, 밑줄 조합 문자열, 한글 보조 표시, 후보창, 클릭 선택.
- `macime/app.py`: InputMethodKit 입력 컨트롤러, marked text, 네이티브 후보창.

변환 규칙과 Mozc 래퍼는 그대로 공유한다. Linux/macOS는 전역 키 훅이나
클립보드 붙여넣기를 사용하지 않고 입력기 프로토콜로 텍스트를 확정한다.
단축키는 조합을 확정한 뒤 앱에 전달한다. Tab은 앱의 포커스 이동 기능을
유지한다. 리셋·포커스 해제 시 남은 조합을 취소한다. OS가 명시적으로
조합 확정을 요청한 경우에는 그 요청에 따른다.

## Linux: IBus

먼저 **IBus를 사용하는 데스크톱 세션**이 필요하다. Ubuntu/GNOME의 IBus
환경을 우선 대상으로 한다. Fcitx5 전용 환경에는 별도 어댑터가 필요하다.
Wayland에서도 전역 훅을 요구하지 않는 구조지만, 데스크톱과 앱이 IBus에
연결되어 있어야 한다. X11/Wayland 전체 앱 호환성을 보장하는 구현은 아니다.

Ubuntu/Debian 예시, 저장소 루트에서 실행:

```sh
sudo apt install ibus python3-gi gir1.2-ibus-1.0 python3-venv
python3 -m venv --system-site-packages .venv-linux
. .venv-linux/bin/activate
# 선택: 한자 사전. 설치하지 않으면 가나만 사용할 수 있다.
python -m pip install -r requirements.txt
python -m linuxime.install
```

`--system-site-packages`가 있어야 시스템 패키지로 설치한 `gi`가 보인다.
설치기는 실행 중인 Python 경로와 코드를 사용자 데이터 폴더에 기록한다.
따라서 설치 후에도 **이 가상환경을 지우거나 옮기지 않는다**.

IBus의 기본 레지스트리는 사용자 component 디렉터리를 검색하지 않는다.
설치기가 출력한 명령으로 XML 한 개를 시스템에 등록한다. 기본 경로 예시:

```sh
sudo install -m 644 "$HOME/.local/share/ibus/component/korkana.xml" \
  /usr/share/ibus/component/korkana.xml
```

`XDG_DATA_HOME`이나 `--data-dir`을 사용했다면 설치기가 출력한 실제 경로를
사용한다. 배포판에 따라 IBus 시스템 데이터 디렉터리도 다를 수 있다.
로그아웃/로그인 후 **설정 → 키보드 → 입력 소스 → 일본어 → KorKana**를
추가한다. 목록에 없는 환경에서는 `ibus-setup`을 확인한다.

관리자 권한 없이 임시로 시험하려면 두 터미널에서 실행한다:

```sh
# 터미널 1, 저장소 루트, 위 가상환경 활성화 상태
python -m linuxime.engine
# 터미널 2, 같은 데스크톱 세션
ibus engine korkana
```

임시 엔진은 터미널 1 프로세스가 종료되면 사라진다. 정식 입력 소스 목록에
노출하려면 XML 등록과 재로그인이 필요하다.

## macOS: InputMethodKit

macOS에서 네이티브 Python 3.10+로 빌드한다. 초기 검증에는 Python 3.12를
권장한다. Apple Silicon과 Intel은 각각 해당 아키텍처의 Python으로 빌드한다.
Windows에서 macOS 앱을 교차 빌드하지 않는다.

저장소 루트에서:

```sh
python3 -m venv .venv-mac
. .venv-mac/bin/activate
python -m pip install -r macime/requirements.txt
# 선택: 한자 사전을 앱에 함께 넣으려면 빌드 전에 설치
python -m pip install -r requirements.txt
python macime/setup.py py2app
mkdir -p "$HOME/Library/Input Methods"
ditto dist/KorKanaIME.app "$HOME/Library/Input Methods/KorKanaIME.app"
```

로그아웃/로그인 후 **시스템 설정 → 키보드 → 텍스트 입력 → 편집 → + → 일본어**에서
KorKana를 추가하고 메뉴 막대에서 선택한다. `python ime.py`로 macOS 입력기를
직접 실행하지 않는다. InputMethodKit은 설치된 `.app`의 번들 설정과 연결 이름을
사용한다. Python과 PyObjC는 py2app 번들에 포함되므로 빌드 후 가상환경은
런타임 의존성이 아니다.

Mozc를 포함한 빌드에서는 MeCab 공유 라이브러리를 앱의 `Contents/Frameworks`에
배치한다. 일부 universal2 MeCab wheel은 긴 설치 이름을 기록할 Mach-O 헤더
공간이 부족하므로, 깊은 Python 확장 디렉터리 대신 이 짧은 경로를 사용한다.
`Input Methods`처럼 공백이 있는 설치 경로도 사전 인자에서 따옴표로 처리한다.
후보창은 서버 전체에서 하나를 유지한다. 입력 컨트롤러마다 만들고 해제하면
컨트롤러 종료 후 서버가 후보창을 참조하는 과정에서 충돌할 수 있다.

배포용 서명·공증, 설치 디스크 이미지, 자동 업데이트는 포함하지 않았다.
외부 배포 전에는 해당 배포 절차와 실제 macOS에서의 입력 소스 등록을 검증한다.
사전을 넣은 빌드에서는 번들 안의 Mozc 사전 데이터도 확인해야 한다.

## 조작

입력 소스를 KorKana로 선택하면 바로 켜진다. 두벌식 QWERTY로 입력한다.
macOS는 물리 키 위치를 사용하며 Caps Lock은 된소리 키로 취급하지 않는다.
Linux는 IBus의 `us` 레이아웃과 Shift 상태를 사용한다.

macOS에서는 가나를 입력하면 한자 후보창이 자동으로 열리고, 계속 입력하거나
지우면 같은 문구의 후보가 갱신된다. Space를 누르면 첫 후보를 선택하고,
다시 누르면 다음 후보로 이동한다. ↑/↓, 숫자, 클릭으로도 선택할 수 있다.
후보를 선택하기 전 Enter는 입력한 가나를 그대로 확정한다. Esc는 후보창을
닫고, 다시 누르면 조합을 취소한다. 가타카나 모드에서는 자동 한자 후보를 숨긴다.

| 키 | 동작 |
|---|---|
| Space | 첫 한자 후보 선택 / 다음 후보 (macOS는 후보창 자동 표시) |
| ↑ / ↓ | 후보 이동 |
| 1–9, 후보 클릭 | 후보 확정 |
| Enter | 현재 가나 또는 선택 후보 확정 |
| Esc | 후보 취소, 다시 누르면 조합 취소 |
| Backspace | 조합 낱자/음절 삭제, 후보창이 있으면 후보 취소 |
| `-` | 장음 `ー` |
| Ctrl+Alt+J | 현재 입력 컨텍스트에서 변환 켜기/끄기 |
| Ctrl+Alt+K | 히라가나/가타카나 |
| Ctrl+Alt+P | 일본어 구두점 치환 켜기/끄기 |

macOS의 Alt는 Option이다. OS나 데스크톱이 먼저 사용하는 단축키는 입력기에
전달되지 않을 수 있다. 입력 소스 전환은 OS 단축키를 사용한다.
Windows의 Ctrl+Alt+Q 종료는 네이티브 입력기 서버를 종료하지 않는다.

## 검증

모든 OS에서:

```sh
python tests/test_kana.py
python -m unittest discover -s tests -p test_native.py -v
python -m unittest discover -s tests -p test_kanji.py -v
# macOS + PyObjC: 네이티브 컨트롤러 종료 후 후보창 수명 회귀 검사
python -m unittest discover -s tests -p test_mac_runtime.py -v
python ime.py --convert 하지메마시떼
python ime.py --convert 라-멘 --katakana
```

기존 `tests/test_ime.py`, `test_layout.py`, `smoke_overlay.py`는 Windows 전용이다.
네이티브 테스트는 사전 결과를 고정해 가나 전용 환경에서도 한자 후보 선택
동작을 검증한다. **실제 Mozc 사전 품질이나 OS 연결을 검증하는 테스트는 아니다.**
`test_kanji.py`는 POSIX에서 실제 Mozc 사전을 공백이 있는 경로에 연결하고 한자
후보가 생성되는지 확인한다. mozcpy가 설치되지 않은 환경에서는 건너뛴다.
Linux에서는 IBus 연결을, macOS에서는 PyObjC 컨트롤러와 앱 빌드를 각각
확인해야 한다. 이 PR에는 GitHub Actions 설정을 포함하지 않았다.

출시 전 각 OS에서 직접 확인할 항목:

1. 입력 소스 등록, 재로그인 후 자동 시작, 종료 후 재시작.
2. `gkwlapaktlEp` → `はじめまして`, Space 후보·숫자 선택·마우스 선택.
3. Shift 모음/된소리, 받침 이동, Backspace, Esc, 긴 입력.
4. 브라우저·텍스트 편집기·터미널에서 Tab/Enter/숫자/기호/단축키 순서.
5. 조합 중 창 전환과 입력 소스 전환, 서로 다른 앱으로 조합이 이동하지 않는지.
6. Linux X11/Wayland 및 macOS Apple Silicon/Intel, 다중 모니터 후보창.
7. 가나 전용 설치와 Mozc 포함 설치, 사전 파일/라이선스 동봉.

로그는 Linux `$XDG_STATE_HOME/KorKanaIME/ime.log`(기본 `~/.local/state/`),
macOS `~/Library/Logs/KorKanaIME/ime.log`에 기록한다.

## 참고 API

- [IBus Engine](https://ibus.github.io/docs/ibus-1.5/IBusEngine.html)
- [IBus 레지스트리 검색 경로 구현](https://github.com/ibus/ibus/blob/main/src/ibusregistry.c)
- [Apple IMKInputController](https://developer.apple.com/documentation/inputmethodkit/imkinputcontroller)
- [Apple IMKCandidates](https://developer.apple.com/documentation/inputmethodkit/imkcandidates)
- [PyObjC InputMethodKit](https://pyobjc.readthedocs.io/en/latest/apinotes/InputMethodKit.html)
