BASE27_CHARS = "0123456789abcdefghijklmnopq"
BASE3_PUA_START = 0xE220   # 0xE220 ~ 0xE23A
BASE27_PUA_START = 0xE200  # 0xE200 ~ 0xE21A

def print_aligned_rows(title: str, items: list, col_width: int = 7):
    print(title)
    chunks = [items[i:i + 10] for i in range(0, len(items), 10)]
    for chunk in chunks:
        line = "".join(f"{item:<{col_width}}" for item in chunk).rstrip()
        print(line)

def print_reference_table():
    # 1. [27진수]: 아스키 0~9, a~q
    b27_ascii = [f"{ch}({i})" for i, ch in enumerate(BASE27_CHARS)]
    print_aligned_rows("[27진수]", b27_ascii, col_width=7)
    print("27진수를 직관적으로 이해하기 어렵다")
    print()

    # 2. [Base3 표현]: 0xE220 ~ 0xE23A + (000) ~ (222)
    b3_items = [
        f"{chr(BASE3_PUA_START + i)}({i // 9}{(i % 9) // 3}{i % 3})"
        for i in range(27)
    ]
    print_aligned_rows("[Base3 표현]", b3_items, col_width=7)
    print("AiJungEum: 이응은 0, 모음ㅣ는 1, 모음ㅡ는 -1 로, LLM 3진법 가중치 3가지 상태를 표현")
    print()

    # 3. [Base27 표현]: 0xE200 ~ 0xE21A + (0) ~ (26)
    b27_items = [
        f"{chr(BASE27_PUA_START + i)}({i})"
        for i in range(27)
    ]
    print_aligned_rows("[Base27 표현]", b27_items, col_width=7)
    print("AiJungEum: 10은 모음 으를 붙이고, 20은 모음 오를 붙인다")
    print("10진수에 익숙한 표현. 직관적으로 이해할수 있다") 

if __name__ == "__main__":
    print_reference_table()
