#!/usr/bin/env python3
"""
desc: text <-> AiJungEum (PUA)

ex:
    $ python3 trans_aijungeum.py "안녕하세요 hello"
    $ python3 trans_aijungeum.py <PUA>
    $ python3 trans_aijungeum.py hex ffff
    $ python3 trans_aijungeum.py dehex <PUA>
    $ python3 trans_aijungeum.py pack helloworld123
    $ python3 trans_aijungeum.py unpack <PUA> 
    $ python3 trans_aijungeum.py raw <PUA>
"""

__author__ = "aijungeum <aijungeum.com> <aijungeum@gmail.com>"
__version__ = "0.1.2.alpha"
__date__ = "2026-11-19"
__license__ = "MIT"

import sys
import zlib

# 표현 유니코드 영역 정의
# PUA-A: U+F0000 ~ U+FFEFF (선형 주소 0x0000 ~ 0xFEFF)
# PUA-B: U+100000 ~ U+1000FF (선형 주소 0xFF00 ~ 0xFFFF)
PUA_A_START = 0xF0000
PUA_A_LIMIT = 0xFFEFF
PUA_B_START = 0x100000
PUA_B_LIMIT = 0x1000FF
JUMP_THRESHOLD = 0xFF00


# =====================================================================
# [Layer 1] 선형 16비트 바이너리(0x0000~0xFFFF) <-> PUA 표현
# =====================================================================

def offset_to_pua(offset: int) -> str:
    """16비트 선형 주소(0x0000~0xFFFF)를 표현용. PUA-A/B 문자로 변환"""
    if offset < JUMP_THRESHOLD:
        return chr(PUA_A_START + offset)
    return chr(PUA_B_START + (offset & 0xFF))


def pua_to_offset(cp: int) -> int:
    """표현용 PUA-A/B 코드포인트를 원래의 선형 16비트 주소(0x0000~0xFFFF)로 복원"""
    if PUA_A_START <= cp <= PUA_A_LIMIT:
        return cp - PUA_A_START
    if PUA_B_START <= cp <= PUA_B_LIMIT:
        return JUMP_THRESHOLD | (cp & 0xFF)
    return -1


def is_valid_pua_char(ch: str) -> bool:
    """유효한 AiJungEum PUA-A 또는 PUA-B 문자인지 체크"""
    cp = ord(ch)
    return (PUA_A_START <= cp <= PUA_A_LIMIT) or (PUA_B_START <= cp <= PUA_B_LIMIT)


def bytes_to_pua(linear_bytes: bytes, add_space: bool = False) -> str:
    """
    [바이너리 -> 표현] 2바이트 단위의 선형 주소(0x0000~0xFFFF)를 PUA 문자열로 변환.
    홀수 바이트가 들어올 경우 끝에 0x00 1바이트를 패딩하여 2바이트 정렬을 유지.
    """
    if len(linear_bytes) % 2 != 0:
        linear_bytes += b'\x00'

    encoded_chars = [
        offset_to_pua((linear_bytes[i] << 8) | linear_bytes[i + 1])
        for i in range(0, len(linear_bytes), 2)
    ]
    return (" " if add_space else "").join(encoded_chars)


def pua_to_bytes(pua_text: str) -> bytes:
    """
    [표현 -> 바이너리] PUA-A/B 문자열을 원래의 선형 2바이트(0x0000~0xFFFF)로 반환.
    """
    clean_text = "".join(pua_text.split())
    raw_bytes = bytearray()

    for ch in clean_text:
        offset = pua_to_offset(ord(ch))
        if offset >= 0:
            raw_bytes.append((offset >> 8) & 0xFF)
            raw_bytes.append(offset & 0xFF)

    return bytes(raw_bytes)


# =====================================================================
# [Layer 2] 텍스트/헥사/압축 인코딩 및 디코딩
# =====================================================================

def encode_aijungeum(text: str, add_space: bool = False, hex_mode: bool = False) -> str:
    """입력 스트링을 선형 2바이트(자음 4개)로 조합한 뒤 PUA 문자로 인코딩"""
    if hex_mode:
        clean_hex = "".join(text.split())
        if not clean_hex:
            return ""

        remainder = len(clean_hex) % 4
        pad_count = (4 - remainder) % 4
        padded_hex = clean_hex + ('0' * pad_count)

        # 16진수 문자열을 순수 선형 바이트로 변환 + 마지막 2바이트에 패딩 카운트 기록
        linear_bytes = bytearray.fromhex(padded_hex)
        linear_bytes.extend(pad_count.to_bytes(2, 'big'))
        return bytes_to_pua(bytes(linear_bytes), add_space=add_space)

    # 일반 UTF-8 텍스트 -> 선형 바이트 -> PUA 변환
    return bytes_to_pua(text.encode('utf-8'), add_space=add_space)


def decode_aijungeum(encoded_text: str, hex_mode: bool = False) -> str:
    """PUA 문자열을 선형 2바이트로 복원한 뒤 원래의 헥사 또는 UTF-8 텍스트로 디코딩"""
    linear_bytes = pua_to_bytes(encoded_text)
    if not linear_bytes:
        return ""

    if hex_mode:
        if len(linear_bytes) < 4:
            return ""
        # 마지막 2바이트(0x0000~0x0003)에서 패딩 카운트 추출
        pad_count = int.from_bytes(linear_bytes[-2:], 'big')
        full_hex = linear_bytes[:-2].hex().upper()
        return full_hex[:-pad_count] if 0 < pad_count <= 3 else full_hex

    # 홀수 바이트 패딩으로 추가된 마지막 1바이트(0x00) 제거 후 UTF-8 디코딩
    if linear_bytes.endswith(b'\x00'):
        linear_bytes = linear_bytes[:-1]

    return linear_bytes.decode('utf-8', errors='replace')


def pack_aijungeum(text: str, add_space: bool = False) -> str:
    """UTF-8 인코딩 -> zlib 압축 -> 선형 2바이트 패킹 -> PUA 변환"""
    compressed = zlib.compress(text.encode('utf-8'), level=9)
    pad_byte_count = len(compressed) % 2

    linear_bytes = bytearray(compressed)
    if pad_byte_count == 1:
        linear_bytes.append(0x00)

    # 마지막 2바이트에 홀수 패딩 여부(0 또는 1) 기록
    linear_bytes.extend(pad_byte_count.to_bytes(2, 'big'))
    return bytes_to_pua(bytes(linear_bytes), add_space=add_space)


def unpack_aijungeum(encoded_text: str) -> str:
    """PUA -> 선형 2바이트 복원 -> 패딩 제거 -> zlib 압축 해제"""
    linear_bytes = pua_to_bytes(encoded_text)
    if len(linear_bytes) < 4:
        return ""

    pad_byte_count = int.from_bytes(linear_bytes[-2:], 'big')
    compressed = linear_bytes[:-2]

    if pad_byte_count == 1:
        compressed = compressed[:-1]

    decompressed = zlib.decompress(compressed)
    return decompressed.decode('utf-8', errors='replace')


if __name__ == "__main__":
    add_space = True
    valid_modes = ("encode", "decode", "hex", "dehex", "pack", "unpack", "raw")

    first_arg = "".join(sys.argv[1:2]).lower()
    if first_arg in valid_modes:
        mode = first_arg
        user_input = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
    else:
        mode = "auto"
        user_input = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "hello"

    if "\\u" in user_input.lower():
        try:
            user_input = user_input.encode('utf-8').decode('unicode_escape')
        except Exception:
            pass

    print(f"입력값: {repr(user_input)}\n")

    clean_check = "".join(user_input.split())
    is_pua = bool(clean_check) and all(is_valid_pua_char(c) for c in clean_check)

    if mode == "raw":
        # PUA-A / PUA-B 문자를 선형 2바이트(0x0000~0xFFFF)로 직접 반환 확인
        raw_2bytes = pua_to_bytes(user_input)
        print(f"선형 2바이트 반환 (bytes): {raw_2bytes}")
        print(f"선형 16진수 덤프 (hex)  : {raw_2bytes.hex(' ').upper()}")
    elif mode == "pack":
        print("-> zlib 압축 후 AiJungEum 패킹 수행")
        packed = pack_aijungeum(user_input, add_space=add_space)
        codes_text = " ".join(f"U+{ord(c):05X}" for c in packed.replace(" ", ""))
        print(f"패킹 결과 : {packed}")
        print(f"코드포인트: {codes_text}")
        print(f"언패킹 검증: {unpack_aijungeum(packed)}")
    elif mode == "unpack":
        print("-> AiJungEum 언패킹 및 zlib 압축 해제 수행")
        print(f"복원된 스트링: {unpack_aijungeum(user_input)}")
    elif mode == "dehex":
        print(f"[hex_mode=True] 디코딩 복원: {decode_aijungeum(user_input, hex_mode=True)}")
    elif mode == "decode" or (mode == "auto" and is_pua):
        print(f"[hex_mode=False] 디코딩 복원: {decode_aijungeum(user_input, hex_mode=False)}")
    elif mode == "hex":
        try:
            enc_text = encode_aijungeum(user_input, add_space=add_space, hex_mode=True)
        except ValueError:
            print("에러: hex 모드에서는 16진수(0~9, A~F)만 입력할 수 있습니다.")
            sys.exit(1)
        codes_text = " ".join(f"U+{ord(c):05X}" for c in enc_text.replace(" ", ""))
        print(f"[hex_mode=True] 변환 결과 : {enc_text}")
        print(f"[hex_mode=True] 코드포인트: {codes_text}")
        print(f"[hex_mode=True] 선형 바이트: {pua_to_bytes(enc_text).hex(' ').upper()}")
        print(f"[hex_mode=True] 디코딩 복원: {decode_aijungeum(enc_text, hex_mode=True)}")
    else:
        enc_text = encode_aijungeum(user_input, add_space=add_space, hex_mode=False)
        codes_text = " ".join(f"U+{ord(c):05X}" for c in enc_text.replace(" ", ""))
        print(f"[hex_mode=False] 변환 결과 : {enc_text}")
        print(f"[hex_mode=False] 코드포인트: {codes_text}")
        print(f"[hex_mode=False] 선형 바이트: {pua_to_bytes(enc_text).hex(' ').upper()}")
        print(f"[hex_mode=False] 디코딩 복원: {decode_aijungeum(enc_text, hex_mode=False)}")

