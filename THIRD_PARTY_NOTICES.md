# 제3자 고지

이 프로그램 자체는 MIT 라이선스다 ([LICENSE](LICENSE)). 아래는 함께 배포되는
제3자 구성요소의 고지다.

배포물(`KorKanaIME-Setup.exe`, `KorKanaIME-portable.zip`)에는 한자 변환용
사전이 들어 있으므로, 그 사전의 라이선스 조건이 함께 적용된다.
소스 저장소에는 사전이 포함되지 않는다 (`pip install mozcpy` 로 따로 받는다).

---

## mozcpy

가나 → 한자 변환 엔진과 사전 데이터.

| | |
|---|---|
| 출처 | https://github.com/ikegami-yukino/mozcpy |
| 저작자 | Yukino Ikegami |
| 라이선스 | WTFPL (조건 없음) |
| 전문 | [third_party/mozcpy-LICENSE.txt](third_party/mozcpy-LICENSE.txt) |

## Mozc

mozcpy 가 쓰는 사전 데이터(`sys.dic`, `matrix.bin` 등)의 원 출처.

| | |
|---|---|
| 출처 | https://github.com/google/mozc |
| 저작권 | Copyright 2010-2018, Google Inc. All rights reserved. |
| 라이선스 | BSD 3-Clause |
| 전문 | [third_party/mozc-LICENSE.txt](third_party/mozc-LICENSE.txt) |

사전 파일(`src/data/dictionary*`)에는 추가 조건이 붙는다.

- **NAIST** — Copyright 2000–2003 Nara Institute of Science and Technology.
  복제·배포는 허용되나 저작권 고지와 면책 문구를 반드시 동반해야 한다.
- **ICOT Free Software** — 사전 표제어 상당 부분의 출처. 배포 시
  **NO WARRANTY** 조항이 항상 프로그램에 첨부되어야 한다.

두 조건 모두 [third_party/mozc-LICENSE.txt](third_party/mozc-LICENSE.txt)
전문에 들어 있으며, 그 파일은 배포물 안에도 함께 들어간다.
