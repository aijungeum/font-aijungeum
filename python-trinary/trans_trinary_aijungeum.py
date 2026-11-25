# python3 trans_trinary_aijungeum.py "[[0,0,0], [1,0,0], [0,1,2]]"
# python3 trans_trinary_aijungeum.py 0t000120210
# python3 trans_trinary_aijungeum.py 0ts00p     # 0ts 27진수 0~9, a(A)~q(Q)
# python3 trans_trinary_aijungeum.py hello 
# python3 trans_trinary_aijungeum.py ts 0t000120210
# python3 trans_trinary_aijungeum.py base3 0t000120210
# python3 trans_trinary_aijungeum.py base3 0ts00p
# python3 trans_trinary_aijungeum.py base27 0ts00p

import ast
import sys
import struct
import zlib
from typing import List, Union, Tuple

# ==========================================
# PUA 매핑 테이블 및 Base-27 문자셋 정의
# ==========================================
BASE3_PUA_START = 0xE220   # 0xE220 ~ 0xE23A (3진수 3자리 조합 27개: 000 ~ 222)
BASE27_PUA_START = 0xE200  # 0xE200 ~ 0xE21A (27진수 단일 문자 27개: 0 ~ 26)

# Base-27 표준 문자셋 (0~9: 0~9, a~q: 10~26)
BASE27_CHARS = "0123456789abcdefghijklmnopq"
BASE27_MAP = {ch: idx for idx, ch in enumerate(BASE27_CHARS)}

# 데이터 타입 
TYPE_UTF8 = 0
TYPE_BIN = 2
TYPE_BASE3 = 3
TYPE_BASE27 = 27


# ==========================================
# Base-27 (0ts) <-> Trits 변환
# ==========================================
def base27_str_to_trits(b27_str: str) -> List[int]:
    """
    27진수 문자열(0~9, a~q, 대소문자 무관)을 3진수 trits 리스트로 변환
    (27진수 1자리 -> 3진수 3자리)
    """
    if not b27_str:
        raise ValueError("0ts 뒤에는 최소 1자리 이상의 27진수 문자가 필요합니다.")
    
    trits = []
    for ch in b27_str.lower():
        if ch not in BASE27_MAP:
            raise ValueError(f"유효하지 않은 27진수 문자입니다: '{ch}' (허용: 0~9, a~q)")
        val27 = BASE27_MAP[ch]
        trits.extend([val27 // 9, (val27 % 9) // 3, val27 % 3])
    return trits


def trits_to_base27_str(trits: List[int]) -> Tuple[str, List[int]]:
    """
    3진수 trits 리스트를 27진수 문자열(0ts 포맷)과 각 자리의 10진수 인덱스(0~26) 리스트로 변환
    """
    if not trits:
        return "", []
    rem = len(trits) % 3
    padded = trits + ([0] * (3 - rem) if rem != 0 else [])
    
    chars = []
    indices = []
    for i in range(0, len(padded), 3):
        val27 = padded[i] * 9 + padded[i+1] * 3 + padded[i+2]
        chars.append(BASE27_CHARS[val27])
        indices.append(val27)
    return "".join(chars), indices


# ==========================================
# PUA 인코딩 / 디코딩 (Base3 & Base27)
# ==========================================
def trits_to_pua_base3(trits: List[int]) -> str:
    """
    Base-3 PUA 변환 (0xE220 ~ 0xE23A): 3진수 3자리 조합(000~222)을 27개 PUA 글자로 매핑
    """
    if not trits:
        return ""
    rem = len(trits) % 3
    padded = trits + ([0] * (3 - rem) if rem != 0 else [])
    chars = []
    for i in range(0, len(padded), 3):
        idx = padded[i] * 9 + padded[i+1] * 3 + padded[i+2]
        chars.append(chr(BASE3_PUA_START + idx))
    return "".join(chars)


def trits_to_pua_base27(trits: List[int]) -> str:
    """
    Base-27 PUA 변환 (0xE200 ~ 0xE21A): 3진수 3자리를 27진수 1글자로 매핑
    """
    if not trits:
        return ""
    rem = len(trits) % 3
    padded = trits + ([0] * (3 - rem) if rem != 0 else [])
    chars = []
    for i in range(0, len(padded), 3):
        val27 = padded[i] * 9 + padded[i+1] * 3 + padded[i+2]
        chars.append(chr(BASE27_PUA_START + val27))
    return "".join(chars)


def pua_to_trits(pua_str: str) -> Tuple[int, List[int]]:
    """
    PUA 문자열(0xE220~0xE23A 또는 0xE200~0xE21A)을 감지하여 (타입, trits 리스트)로 복원
    """
    trits = []
    detected_type = TYPE_BASE27
    for ch in pua_str:
        code = ord(ch)
        if BASE3_PUA_START <= code <= BASE3_PUA_START + 26:
            detected_type = TYPE_BASE3
            idx = code - BASE3_PUA_START
        elif BASE27_PUA_START <= code <= BASE27_PUA_START + 26:
            detected_type = TYPE_BASE27
            idx = code - BASE27_PUA_START
        else:
            raise ValueError(f"허용되지 않은 PUA 문자입니다: U+{code:04X}")

        trits.extend([idx // 9, (idx % 9) // 3, idx % 3])
    return detected_type, trits


# ==========================================
# 비트 스트림 재분할 (UTF-8 / Bytes <-> Trits)
# ==========================================
def bytes_to_trit_stream(data: bytes) -> List[int]:
    """
    테스트 편의용 변환: 바이트(UTF-8 등)를 하나의 연속된 비트 스트림(정수)으로 보고
    3진수 트릿 배열로 재분할 (선행 0x00 바이트 보존을 위해 0x01 마커 사용)
    """
    if not data:
        return []
    marked = b'\x01' + data
    num = int.from_bytes(marked, 'big')
    trits = []
    while num > 0:
        trits.append(num % 3)
        num //= 3
    trits.reverse()
    return trits


def trit_stream_to_bytes(trits: List[int]) -> bytes:
    """
    트릿 스트림을 원래의 바이트(UTF-8 등)로 복원
    """
    if not trits:
        return b""
    num = 0
    for t in trits:
        if t not in (0, 1, 2):
            raise ValueError(f"유효하지 않은 3진수 값입니다: {t}")
        num = num * 3 + t
    byte_len = (num.bit_length() + 7) // 8
    raw = num.to_bytes(byte_len, 'big')
    if raw[0] != 1:
        raise ValueError("UTF-8/바이너리 스트림 복원 마커가 일치하지 않습니다.")
    return raw[1:]


# ==========================================
# 1바이트 = 5-Trit 에뮬레이터 패킹 / 언패킹 및 zlib 압축
# ==========================================
def pack_trits_5(trits: List[int]) -> Tuple[bytes, int]:
    """
    에뮬레이터 표준 패킹: 3진수 5개씩 묶어 1바이트(0~242)로 패킹 (상위 자릿수 우선).
    마지막 묶음이 5개 미만이면 뒤에 0을 채우고 채운 패딩 개수를 반환.
    """
    if not trits:
        return b"", 0

    rem = len(trits) % 5
    pad_count = (5 - rem) if rem != 0 else 0
    padded_trits = trits + ([0] * pad_count)

    packed = bytearray()
    for i in range(0, len(padded_trits), 5):
        t0, t1, t2, t3, t4 = padded_trits[i:i+5]
        val = (t0 * 81) + (t1 * 27) + (t2 * 9) + (t3 * 3) + t4
        packed.append(val)

    return bytes(packed), pad_count


def unpack_trits_5(packed_bytes: bytes, pad_count: int) -> List[int]:
    """
    1바이트(0~242)를 5개의 3진수 자릿수로 언패킹한 뒤 뒤쪽 패딩 제거
    """
    if not packed_bytes:
        return []

    trits = []
    for val in packed_bytes:
        if val > 242:
            raise ValueError(f"5-Trit 패킹 범위를 초과한 바이트입니다: {val}")
        chunk = [0] * 5
        for i in range(4, -1, -1):
            chunk[i] = val % 3
            val //= 3
        trits.extend(chunk)

    if pad_count > 0:
        if pad_count > len(trits):
            raise ValueError("패딩 개수가 전체 3진수 길이보다 큽니다.")
        trits = trits[:-pad_count]

    return trits


def pack_container(trits: List[int], data_type: int = TYPE_BASE3) -> bytes:
    """
    컨테이너 포맷: [4바이트 길이] + zlib([1바이트 타입] + [5-trit 패킹 바이트] + [1바이트 패딩 개수])
    """
    packed_body, pad_count = pack_trits_5(trits)
    payload = bytes([data_type]) + packed_body + bytes([pad_count])
    compressed = zlib.compress(payload)
    length_prefix = struct.pack(">I", len(compressed))
    return length_prefix + compressed


def unpack_container(container: bytes) -> Tuple[int, List[int]]:
    """
    zlib 압축 해제 및 5-Trit 언패킹 후 (데이터 타입, 복원된 trits 리스트) 반환
    """
    if len(container) < 4:
        raise ValueError("error: container len : short")
    comp_len = struct.unpack(">I", container[:4])[0]
    compressed = container[4:4 + comp_len]
    if len(compressed) != comp_len:
        raise ValueError("invalid container length")

    payload = zlib.decompress(compressed)
    if len(payload) < 2:
        raise ValueError("invalid decompressed payload")

    data_type = payload[0]
    pad_count = payload[-1]
    packed_body = payload[1:-1]
    trits = unpack_trits_5(packed_body, pad_count)
    return data_type, trits

# ==========================================
# 통합 입력 파서 (3진수 에뮬레이션 데이터 & 테스트용 UTF-8/Hex/Bin)
# ==========================================
def parse_input(user_input: Union[str, List[List[int]], List[int]]) -> Tuple[int, bytes, List[int]]:
    """
    모든 입력을 3진수 trits 리스트와 5-Trit 패킹 바이트로 변환하여
    (data_type, packed_5trit_bytes, trits) 형태로 반환
    """
    # 리스트 입력: [[0, 1, 2], [1, 2, 0]] 또는 [0, 1, 2, 1, 2, 0]
    if isinstance(user_input, list):
        if user_input and isinstance(user_input[0], list):
            flat_trits = [t for group in user_input for t in group]
        else:
            flat_trits = list(user_input)

        if any(t not in (0, 1, 2) for t in flat_trits):
            raise ValueError("3진수 리스트 요소는 0, 1, 2만 가능합니다.")
        packed_bytes, _ = pack_trits_5(flat_trits)
        return TYPE_BASE3, packed_bytes, flat_trits

    # 문자열 입력 처리
    if isinstance(user_input, str):
        s = user_input.strip()

        # 1) CLI에서 문자열로 전달된 2차원 리스트 파싱 (예: "[[0,1,2], [1,2,0]]")
        if s.startswith("[[") and s.endswith("]]"):
            parsed_list = ast.literal_eval(s)
            return parse_input(parsed_list)

        # 2) PUA 문자열이 포함된 경우 자동 복원
        if s and all((BASE27_PUA_START <= ord(c) <= BASE27_PUA_START + 26) or
                     (BASE3_PUA_START <= ord(c) <= BASE3_PUA_START + 26) for c in s):
            dtype, trits = pua_to_trits(s)
            packed_bytes, _ = pack_trits_5(trits)
            return dtype, packed_bytes, trits

        # 3) 0ts 접두사 (27진수 직접 입력: 0~9, a~q) -> 0t 보다 먼저 검사
        if s.startswith("0ts"):
            b27_str = s[3:]
            trits = base27_str_to_trits(b27_str)
            packed_bytes, _ = pack_trits_5(trits)
            return TYPE_BASE27, packed_bytes, trits

        # 4) 0t 접두사 (3진수 직접 입력)
        if s.startswith("0t"):
            t_str = s[2:]
            if not t_str or any(c not in "012" for c in t_str):
                raise ValueError("0t 뒤에는 0, 1, 2만 입력할 수 있습니다.")
            trits = [int(c) for c in t_str]
            packed_bytes, _ = pack_trits_5(trits)
            return TYPE_BASE3, packed_bytes, trits

        # 5) 0x 접두사
        if s.startswith("0x"):
            hex_str = s[2:]
            if len(hex_str) % 2 != 0:
                hex_str = "0" + hex_str
            raw_bytes = bytes.fromhex(hex_str)
            trits = bytes_to_trit_stream(raw_bytes)
            packed_bytes, _ = pack_trits_5(trits)
            return TYPE_BIN, packed_bytes, trits

        # 6) 0b 접두사
        if s.startswith("0b"):
            bin_str = s[2:]
            byte_len = (len(bin_str) + 7) // 8
            raw_bytes = int(bin_str, 2).to_bytes(byte_len, 'big')
            trits = bytes_to_trit_stream(raw_bytes)
            packed_bytes, _ = pack_trits_5(trits)
            return TYPE_BIN, packed_bytes, trits

        # 7) 일반 UTF-8 문자열 (테스트 편의용 -> 비트 스트림 재분할)
        raw_bytes = user_input.encode("utf-8")
        trits = bytes_to_trit_stream(raw_bytes)
        packed_bytes, _ = pack_trits_5(trits)
        return TYPE_UTF8, packed_bytes, trits

    raise TypeError("unsupported input type")


# ==========================================
# 출력 (print_ts, print_utf8, print3, print27)
# ==========================================
def print_ts(user_input: Union[str, List[List[int]], List[int]]) -> str:
    """
    27진수(0ts) 문자열과 함께 가독성을 위해 각 자리의 10진수 값(0~26)을 병기 출력
    """
    _, _, trits = parse_input(user_input)
    b27_str, indices = trits_to_base27_str(trits)
    
    breakdown = " ".join(f"{ch}({idx})" for ch, idx in zip(b27_str, indices))
    print(f"[0ts 표기]: 0ts{b27_str}  ->  [{breakdown}]")
    return f"0ts{b27_str}"


def print_utf8(data: Union[List[int], str]) -> str:
    """트릿 스트림(또는 PUA 문자열)을 원본 UTF-8 문자열로 복원 및 출력"""
    if isinstance(data, str):
        _, _, trits = parse_input(data)
    elif isinstance(data, list):
        trits = data
    else:
        raise TypeError("unsupported data type")

    raw_bytes = trit_stream_to_bytes(trits)
    try:
        decoded = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        decoded = f"<Binary Bytes: 0x{raw_bytes.hex()}>"

    print(f"[UTF-8]  : {decoded}")
    return decoded


def print3(user_input: Union[str, List[List[int]], List[int]]) -> str:
    """Base-3 PUA (0xE220 ~ 0xE23A), 10진수 인덱스, 3진수 조합(000~222), 유니코드 출력"""
    _, _, trits = parse_input(user_input)
    pua3 = trits_to_pua_base3(trits)
    indices = [ord(c) - BASE3_PUA_START for c in pua3]
    
    # 각 인덱스(0~26)를 3자리 3진수 문자열('000' ~ '222')로 변환
    trit_groups = ",".join(f"{idx // 9}{(idx % 9) // 3}{idx % 3}" for idx in indices)
    codes = " ".join(f"U+{ord(c):04X}" for c in pua3)
    
    print(f"[Base3]  : {pua3}  {indices} ({trit_groups}) ({codes})")
    return pua3



def print27(user_input: Union[str, List[List[int]], List[int]]) -> str:
    """Base-27 PUA (0xE200 ~ 0xE21A) 및 인덱스(0~26) 리스트 출력"""
    _, _, trits = parse_input(user_input)
    pua27 = trits_to_pua_base27(trits)
    indices = [ord(c) - BASE27_PUA_START for c in pua27]
    codes = " ".join(f"U+{ord(c):04X}" for c in pua27)
    print(f"[Base27] : {pua27}  {indices} ({codes})")
    return pua27


# ==========================================
# 동작 검증
# ==========================================
def main():
    args = sys.argv[1:]

    if not args:
        print("사용법:")
        print("  python3 trans_trinary_aijungeum.py <text | 0t... | 0ts... | 0x... | '[[0,1,2],...]' | PUA>")
        print("  python3 trans_trinary_aijungeum.py ts <chars>")
        print("  python3 trans_trinary_aijungeum.py base3 <chars>")
        print("  python3 trans_trinary_aijungeum.py base27 <chars>")
        print("  python3 trans_trinary_aijungeum.py decode <PUA_chars>")
        return

    cmd = args[0]

    if cmd == "ts" and len(args) >= 2:
        target = " ".join(args[1:])
        print_ts(target)

    elif cmd == "base3" and len(args) >= 2:
        target = " ".join(args[1:])
        print3(target)

    elif cmd == "base27" and len(args) >= 2:
        target = " ".join(args[1:])
        print27(target)

    elif cmd == "decode" and len(args) >= 2:
        target = " ".join(args[1:])
        print_utf8(target)

    else:
        target = " ".join(args)
        dtype, packed_5trit, trits = parse_input(target)

        print(f"=== 입력: {target} ===")
        print(f"[0t 표기]: 0t{''.join(map(str, trits))} (총 {len(trits)} trits)")
        print_ts(trits)
        print(f"[5-Trit] : 0x{packed_5trit.hex()} ({len(packed_5trit)} bytes, 1바이트당 5트릿 패킹)")
        print3(trits)
        print27(trits)

        # pack/unpack
        container = pack_container(trits, data_type=dtype)
        restored_type, unpacked_trits = unpack_container(container)
        assert trits == unpacked_trits, "압축/해제 데이터 불일치!"
        print(f"[Zlib]   : 총 {len(container)} bytes (Type={restored_type}, 압축/복원 검증 완료)")

        # UTF-8/바이너리 테스트 입력인 경우, 원본 복원/출력
        if dtype in (TYPE_UTF8, TYPE_BIN):
            print_utf8(unpacked_trits)


if __name__ == "__main__":
    main()


