# -*- coding: utf-8 -*-
"""변환 규칙 회귀 테스트.  실행: python tests/test_kana.py"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from korkana import HangulComposer, convert, to_katakana

# ---------------------------------------------------------------- 한글 -> 가나
KANA_CASES = [
    # 기본 인사
    ("하지메마시떼", "はじめまして"),
    ("콘니치와", "こんにちわ"),
    ("아리가또우", "ありがとう"),
    ("사요나라", "さよなら"),
    ("오하요우", "おはよう"),
    ("스미마셍", "すみません"),
    ("이타다키마스", "いただきます"),
    # 청음/탁음 구분 (격음 = 청음, 평음 = 탁음)
    ("카", "か"), ("가", "が"),
    ("타", "た"), ("다", "だ"),
    ("파", "ぱ"), ("바", "ば"),
    ("까", "か"), ("따", "た"), ("빠", "ぱ"),
    # ㅜ / ㅡ 구분
    ("주", "じゅ"), ("즈", "ず"),
    ("추", "ちゅ"), ("츠", "つ"),
    ("투", "とぅ"), ("트", "つ"),
    # 촉음
    ("킷떼", "きって"),
    ("잇쇼", "いっしょ"),
    ("촛또", "ちょっと"),
    ("맛차", "まっちゃ"),
    # 발음 ん
    ("센세이", "せんせい"),
    ("싱붕", "しんぶん"),
    ("암마", "あんま"),
    # 종성 ㄹ -> る
    ("파일", "ぱいる"),
    ("메일", "めいる"),
    # 요음
    ("쿄우", "きょう"),
    ("샤신", "しゃしん"),
    ("뉴우스", "にゅうす"),
    ("죠우즈", "じょうず"),
    # 외래음
    ("화", "ふぁ"), ("휘", "ふぃ"), ("훼", "ふぇ"), ("훠", "ふぉ"),
    ("티", "てぃ"), ("디", "でぃ"),
    ("워", "を"),
    # 장음 부호
    ("라-멘", "らーめん"),
    ("코-히-", "こーひー"),
    # 비한글 통과
    ("아 이", "あ い"),
    ("abc123", "abc123"),
    ("오늘? 네!", "おぬる? ね!"),
]

# ---------------------------------------------------------------- 가타카나
KATAKANA_CASES = [
    ("라-멘", "ラーメン"),
    ("콤퓨-타-", "コンピューター"),
    ("테레비", "テレビ"),
    ("코-히-", "コーヒー"),
]

# ---------------------------------------------------------------- QWERTY -> 한글
# 두벌식으로 실제 타자하는 키 시퀀스. 대문자는 shift.
TYPING_CASES = [
    ("gkwlapaktlEp", "하지메마시떼"),
    ("zhsslclwk", "콘니치자"),      # 'wk' = ㅈㅏ
    ("dkflrkEh", "아리가또"),
    ("tptpdl", "세세이"),
    ("vkdlf", "파일"),
]


def run():
    fails = []

    for src, want in KANA_CASES:
        got = convert(src)
        if got != want:
            fails.append(f"convert({src!r}) -> {got!r}, 기대 {want!r}")

    for src, want in KATAKANA_CASES:
        got = convert(src, katakana=True)
        if got != want:
            fails.append(f"convert({src!r}, katakana) -> {got!r}, 기대 {want!r}")

    for keys, want in TYPING_CASES:
        comp = HangulComposer()
        parts = []
        for ch in keys:
            done, handled = comp.feed_key(ch, shift=ch.isupper())
            assert handled, f"키 {ch!r} 처리 실패"
            parts += done
        parts.append(comp.flush())
        got = "".join(parts)
        if got != want:
            fails.append(f"typing({keys!r}) -> {got!r}, 기대 {want!r}")

    # 백스페이스: 떼 -> ㄸ -> (빈 상태)
    comp = HangulComposer()
    comp.feed("ㄸ"); comp.feed("ㅔ")
    if comp.pending() != "떼":
        fails.append(f"pending -> {comp.pending()!r}, 기대 '떼'")
    comp.backspace()
    if comp.pending() != "ㄸ":
        fails.append(f"backspace 1 -> {comp.pending()!r}, 기대 'ㄸ'")
    comp.backspace()
    if not comp.is_empty():
        fails.append(f"backspace 2 -> {comp.pending()!r}, 기대 빈 상태")
    if comp.backspace():
        fails.append("빈 상태 backspace 가 True 를 반환")

    # 복합 모음/겹받침 결합
    comp = HangulComposer()
    for j in "ㄱㅗㅏㄴ":
        comp.feed(j)
    if comp.pending() != "관":
        fails.append(f"ㅗ+ㅏ 결합 -> {comp.pending()!r}, 기대 '관'")

    total = len(KANA_CASES) + len(KATAKANA_CASES) + len(TYPING_CASES) + 5
    if fails:
        print(f"FAIL  {len(fails)}/{total}")
        for f in fails:
            print("  -", f)
        return 1
    print(f"PASS  {total} cases")
    return 0


if __name__ == "__main__":
    sys.exit(run())
