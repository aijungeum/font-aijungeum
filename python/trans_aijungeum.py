#!/usr/bin/env python3
"""
desc: Linear 16-bit Binary Codec & Pack <-> AiJungEum (PUA Display Only)

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
__version__ = "0.1.3.alpha"
__date__ = "2026-11-19"
__license__ = "MIT"

import sys
import zlib

# =====================================================================
# 상수 및 헤더 정의
# =====================================================================
# AiJungEum 바이너리 식별 매직 헤더 (4바이트 = 선형 2글자 분량)
# 'AJE' (3바이트) + Flags/Version (1바이트)
MAGIC_PREFIX = b"AJE"
FLAG_RAW_UTF8 = 0x01  # 일반 UTF-8 선형 패킹
FLAG_ZLIB     = 0x02  # zlib 압축 선형 패킹
FLAG_HEX      = 0x03  # 16진수 선형 패킹
PAD_BIT_MASK  = 0x80  # 최상위 비트(MSB): 홀수 바이트 0x00 패딩 여부 표시

# 표현 유니코드 영역 정의 (Display Layer 전용)
PUA_A_START = 0xF0000
PUA_A_LIMIT = 0xF7FFF
PUA_B_START = 0x100000
PUA_B_LIMIT = 0x107FFF
JUMP_THRESHOLD = 0x8000


# =====================================================================
# [Layer 1] Core Linear Binary Codec & Pack (용량 최적화: 2바이트 단위)
# =====================================================================

def _align_even_bytes(data: bytes) -> tuple[bytes, bool]:
    """선형 16비트 주소(2바이트) 정렬을 위해 홀수 길이면 끝에 0x00 1바이트 패딩"""
    if len(data) % 2 != 0:
        return data + b"\x00", True
    return data, False


def pack_linear(payload: bytes, compress: bool = False, is_hex: bool = False) -> bytes:
    """
    [코어 패커] 데이터를 선형 16비트(2바이트) 정렬된 바이너리 컨테이너로 패킹.
    구조: [MAGIC(3B: 'AJE')] + [FLAGS(1B)] + [ALIGNED_PAYLOAD(2N Bytes)]
    """
    if is_hex:
        mode_flag = FLAG_HEX
    elif compress:
        payload = zlib.compress(payload, level=9)
        mode_flag = FLAG_ZLIB
    else:
        mode_flag = FLAG_RAW_UTF8

    aligned_payload, is_padded = _align_even_bytes(payload)
    if is_padded:
        mode_flag |= PAD_BIT_MASK

    header = MAGIC_PREFIX + bytes([mode_flag])  # 정확히 4바이트 (선형 2워드)
    return header + aligned_payload


def unpack_linear(container: bytes) -> tuple[bytes, int]:
    """
    [코어 언패커] 'AJE' 매직 헤더를 검증하고 원본 바이트와 모드 플래그를 복원.
    """
    if len(container) < 4 or not container.startswith(MAGIC_PREFIX):
        raise ValueError("유효한 AiJungEum(AJE) 선형 바이너리 헤더가 아닙니다.")

    raw_flag = container[3]
    is_padded = bool(raw_flag & PAD_BIT_MASK)
    mode_flag = raw_flag & ~PAD_BIT_MASK

    payload = container[4:]
    if is_padded and payload.endswith(b"\x00"):
        payload = payload[:-1]

    if mode_flag == FLAG_ZLIB:
        payload = zlib.decompress(payload)

    return payload, mode_flag


def encode_linear_text(text: str, compress: bool = False) -> bytes:
    """텍스트 -> 선형 바이너리 컨테이너 (PUA 미사용, 최소 용량)"""
    return pack_linear(text.encode("utf-8"), compress=compress, is_hex=False)


def decode_linear_text(container: bytes) -> str:
    """선형 바이너리 컨테이너 -> 원본 텍스트 복원"""
    payload, mode_flag = unpack_linear(container)
    if mode_flag == FLAG_HEX:
        return payload.hex().upper()
    return payload.decode("utf-8", errors="replace")


def encode_linear_hex(hex_str: str) -> bytes:
    """16진수 문자열 -> 선형 바이너리 컨테이너"""
    clean_hex = "".join(hex_str.split())
    if not clean_hex:
        return b""
    if len(clean_hex) % 2 != 0:
        raise ValueError("16진수 입력은 바이트 단위(짝수 길이)여야 합니다.")
    return pack_linear(bytes.fromhex(clean_hex), compress=False, is_hex=True)


# =====================================================================
# [Layer 2] Display Adapter (출력 시에만 PUA 변환 / 입력 시 PUA 파싱)
# =====================================================================

def offset_to_pua(offset: int) -> str:
    """16비트 선형 주소(0x0000~0xFFFF) -> PUA-A/B 문자"""
    if offset < JUMP_THRESHOLD:
        return chr(PUA_A_START + offset)
    return chr(PUA_B_START + (offset & 0x7FFF))


def pua_to_offset(cp: int) -> int:
    """PUA-A/B 코드포인트 -> 16비트 선형 주소(0x0000~0xFFFF)"""
    if PUA_A_START <= cp <= PUA_A_LIMIT:
        return cp - PUA_A_START
    if PUA_B_START <= cp <= PUA_B_LIMIT:
        return JUMP_THRESHOLD | (cp & 0x7FFF)
    return -1


def is_valid_pua_char(ch: str) -> bool:
    cp = ord(ch)
    return (PUA_A_START <= cp <= PUA_A_LIMIT) or (PUA_B_START <= cp <= PUA_B_LIMIT)


def bytes_to_pua_display(linear_bytes: bytes, add_space: bool = False) -> str:
    """[출력 전용] 선형 2바이트 열을 화면 표시용 PUA 문자열로 렌더링"""
    aligned, _ = _align_even_bytes(linear_bytes)
    chars = [
        offset_to_pua((aligned[i] << 8) | aligned[i + 1])
        for i in range(0, len(aligned), 2)
    ]
    return (" " if add_space else "").join(chars)


def pua_display_to_bytes(pua_text: str) -> bytes:
    """[입력 전용] 화면의 PUA 문자열을 선형 2바이트 바이너리로 파싱"""
    clean_text = "".join(pua_text.split())
    raw = bytearray()
    for ch in clean_text:
        offset = pua_to_offset(ord(ch))
        if offset >= 0:
            raw.append((offset >> 8) & 0xFF)
            raw.append(offset & 0xFF)
    return bytes(raw)


# =====================================================================
# CLI 실행부
# =====================================================================

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
            user_input = user_input.encode("utf-8").decode("unicode_escape")
        except Exception:
            pass

    print(f"입력값: {repr(user_input)}\n")

    clean_check = "".join(user_input.split())
    is_pua = bool(clean_check) and all(is_valid_pua_char(c) for c in clean_check)

    if mode == "raw":
        raw_bytes = pua_display_to_bytes(user_input)
        print(f"선형 바이너리 (bytes): {raw_bytes}")
        print(f"선형 16진수 덤프     : {raw_bytes.hex(' ').upper()}")
        if raw_bytes.startswith(MAGIC_PREFIX) and len(raw_bytes) >= 4:
            print(f"매직 헤더 감지       : AJE (Flag=0x{raw_bytes[3]:02X})")

    elif mode == "pack":
        # 1. 내부 처리는 순수 선형 바이너리로 패킹 (용량 최소화)
        linear_bin = encode_linear_text(user_input, compress=True)
        # 2. 화면에 보여줄 때만 PUA로 변환
        pua_view = bytes_to_pua_display(linear_bin, add_space=add_space)
        print(f"[선형 바이너리] 크기: {len(linear_bin)} bytes (헤더 4B 포함)")
        print(f"[선형 바이너리] HEX : {linear_bin.hex(' ').upper()}")
        print(f"[PUA 출력]          : {pua_view}")
        print(f"[언패킹 검증]       : {decode_linear_text(pua_display_to_bytes(pua_view))}")

    elif mode == "unpack" or (mode == "auto" and is_pua):
        linear_bin = pua_display_to_bytes(user_input)
        try:
            restored = decode_linear_text(linear_bin)
            print(f"복원 결과: {restored}")
        except ValueError as e:
            print(f"에러: {e}")

    elif mode == "hex":
        try:
            linear_bin = encode_linear_hex(user_input)
        except ValueError as e:
            print(f"에러: {e}")
            sys.exit(1)
        pua_view = bytes_to_pua_display(linear_bin, add_space=add_space)
        print(f"[선형 바이너리] 크기: {len(linear_bin)} bytes")
        print(f"[선형 바이너리] HEX : {linear_bin.hex(' ').upper()}")
        print(f"[PUA 출력]          : {pua_view}")
        print(f"[디코딩 검증]       : {decode_linear_text(linear_bin)}")

    elif mode == "dehex":
        linear_bin = pua_display_to_bytes(user_input)
        print(f"복원 HEX: {decode_linear_text(linear_bin)}")

    else:
        # 일반 encode 모드
        linear_bin = encode_linear_text(user_input, compress=False)
        pua_view = bytes_to_pua_display(linear_bin, add_space=add_space)
        print(f"[선형 바이너리] 크기: {len(linear_bin)} bytes (PUA UTF-8 대비 {len(linear_bin)}B vs {len(pua_view.replace(' ', '').encode('utf-8'))}B)")
        print(f"[선형 바이너리] HEX : {linear_bin.hex(' ').upper()}")
        print(f"[PUA 출력]          : {pua_view}")
        print(f"[디코딩 검증]       : {decode_linear_text(linear_bin)}")
