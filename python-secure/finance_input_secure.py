# 암호화 부분을 제외하고. 
# 금융 비밀번호 설정시, 최초, 사용자가 진수를 선택하고, 10진수로 보이는 숫자 입력. 
#   사용자는 10진수만 기억하면 된다. 타인이 엿보거나, DB가 유출되도 어떤 진수인지 알수 없다 
#
# python3 finance_input_secure.py 0ts00q
# python3 finance_input_secure.py -t ts 00q
# python3 finance_input_secure.py -t hex FF
# python3 finance_input_secure.py -t dec 123


import argparse
import sys

BASE27_CHARS = "0123456789abcdefghijklmnopq"
BASE27_MAP = {ch: idx for idx, ch in enumerate(BASE27_CHARS)}


def parse_base27(value_str: str) -> int:
    """27진수 문자열(0~9, a~q)을 10진수 정수로 변환"""
    s = value_str.strip().lower()
    if s.startswith("0ts"):
        s = s[3:]
    if not s:
        raise ValueError("27진수 값이 비어 있습니다.")

    result = 0
    for ch in s:
        if ch not in BASE27_MAP:
            raise ValueError(f"허용되지 않은 27진수 문자입니다: '{ch}' (허용: 0~9, a~q)")
        result = result * 27 + BASE27_MAP[ch]
    return result


def to_base27(num: int) -> str:
    """10진수 정수를 27진수 문자열(0ts...)로 변환"""
    if num < 0:
        raise ValueError("음수는 27진수로 변환할 수 없습니다.")
    if num == 0:
        return "0ts0"

    digits = []
    while num > 0:
        num, rem = divmod(num, 27)
        digits.append(BASE27_CHARS[rem])
    return "0ts" + "".join(reversed(digits))


def parse_input_number(raw_value: str, input_type: str = "auto") -> int:
    """입력 타입 파라미터(auto, dec, hex, ts)에 따라 정수로 파싱"""
    s = raw_value.strip()
    if not s:
        raise ValueError("입력값이 비어 있습니다.")

    mode = input_type.lower()

    if mode == "auto":
        lower_s = s.lower()
        if lower_s.startswith("0ts"):
            return parse_base27(s)
        if lower_s.startswith("0x"):
            return int(s, 16)
        return int(s, 10)

    if mode in ("dec", "10"):
        return int(s, 10)
    if mode in ("hex", "16"):
        return int(s, 16)
    if mode in ("ts", "base27", "27"):
        return parse_base27(s)

    raise ValueError(f"지원하지 않는 입력 타입입니다: {input_type}")


def format_outputs(num: int) -> None:
    """10진수, 16진수, 27진수 형식으로 출력"""
    if num < 0:
        raise ValueError("0 이상의 정수만 지원합니다.")

    print(f"10진수 : {num}")
    print(f"16진수 : 0x{num:X}")
    print(f"27진수 : {to_base27(num)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="10진수, 16진수(0x), 27진수(0ts) 상호 변환기"
    )
    parser.add_argument(
        "value",
        help="변환할 숫자 (예: 123, 0xFF, 0ts00q)"
    )
    parser.add_argument(
        "-t", "--type",
        dest="input_type",
        default="auto",
        choices=["auto", "dec", "10", "hex", "16", "ts", "base27", "27"],
        help="입력 진법 강제 지정 (기본값: auto)"
    )

    args = parser.parse_args()

    try:
        num = parse_input_number(args.value, args.input_type)
        format_outputs(num)
    except ValueError as e:
        print(f"[입력 오류] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

