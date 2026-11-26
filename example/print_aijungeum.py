#!/usr/bin/env python3
import random

PUA_A_START = 0xF0000
PUA_A_LIMIT = 0xF7FFF  # 32,768개 (0xF0000 ~ 0xF7FFF)
PUA_B_START = 0x100000
PUA_B_LIMIT = 0x107FFF  # 32,768개 (0x100000 ~ 0x107FFF)
JUMP_THRESHOLD = 0x8000


def offset_to_pua(offset: int) -> int:
    if offset < JUMP_THRESHOLD:
        return PUA_A_START + offset
    return PUA_B_START + (offset & 0x7FFF)


def main():
    # 1. 필수 고정 주소 (PUA-A 시작/끝, PUA-B 시작/끝)
    fixed_offsets = [
        ("PUA-A 첫 주소 (0x0000)", 0x0000),
        ("PUA-A 끝 주소 (0x7FFF)", 0x7FFF),
        ("PUA-B 첫 주소 (0x8000)", 0x8000),
        ("PUA-B 끝 주소 (0xFFFF)", 0xFFFF),
    ]

    # 2. 중간 구간(0x0001 ~ 0xFFFE)에서 랜덤 20개 추출 후 정렬
    middle_pool = [o for o in range(0x0001, 0xFFFF) if o not in (0x7FFF, 0x8000)]
    random_offsets = sorted(random.sample(middle_pool, 20))

    print("=== [필수 경계 주소 확인] ===")
    for label, off in fixed_offsets:
        cp = offset_to_pua(off)
        print(f"{label:<24} | U+{cp:06X} | {chr(cp)}")

    print("\n=== [중간 구간 랜덤 20개 확인] ===")
    for off in random_offsets:
        cp = offset_to_pua(off)
        part = "PUA-A" if off < JUMP_THRESHOLD else "PUA-B"
        print(f"[{part}] offset=0x{off:04X} | U+{cp:06X} | {chr(cp)}")

    # 한 줄 복사 테스트용 문자열 출력
    all_chars = [chr(offset_to_pua(off)) for _, off in fixed_offsets] + [
        chr(offset_to_pua(off)) for off in random_offsets
    ]
    print("\n=== [한 줄 복사 테스트용] ===")
    print(" ".join(all_chars))


if __name__ == "__main__":
    main()
