#!/usr/bin/env python3
"""
desc: text <-> AiJungEum (PUA)

ex:
    $ python3 trans_aijungeum.py "안녕하세요 hello"
    $ python3 trans_aijungeum.py <PUA>
    $ python3 trans_aijungeum.py encode "hello"
    $ python3 trans_aijungeum.py hex 00000
    $ python3 trans_aijungeum.py dehex <PUA>
    $ python3 trans_aijungeum.py pack helloworld123
    $ python3 trans_aijungeum.py unpack <PUA> 
"""

__author__ = "aijungeum <aijungeum.com> <aijungeum@gmail.com>" 
__version__ = "0.1.0.alpha"
__date__ = "2026-11-19"
__license__ = "MIT"

import sys
import zlib

PUA_START = 0xF0000


def encode_aijungeum(text: str, add_space: bool = False, hex_mode: bool = False) -> str:
    """
    입력 스트링을 PUA 문자로 인코딩.
    - add_space=True: pretty print 
    - hex_mode=False: 일반 텍스트(UTF-8) 인코딩
    - hex_mode=True: 16진수 헥사 스트링 직접 매핑 + 마지막 1글자(2바이트) 패딩 카운트 기록
    """
    encoded_chars = list()

    if hex_mode:
        clean_hex = "".join(text.split())
        if not clean_hex:
            return ""

        remainder = len(clean_hex) % 4
        pad_count = (4 - remainder) % 4
        padded_hex = clean_hex + ('0' * pad_count)

        for i in range(0, len(padded_hex), 4):
            n1 = int(padded_hex[i], 16)
            n2 = int(padded_hex[i+1], 16)
            n3 = int(padded_hex[i+2], 16)
            n4 = int(padded_hex[i+3], 16)
            pua_code = PUA_START + (n1 << 12) + (n2 << 8) + (n3 << 4) + n4
            encoded_chars.append(chr(pua_code))

        # 전체 변환 완료 후 맨 마지막에 패딩 개수(0~3) 1글자 추가
        encoded_chars.append(chr(PUA_START + pad_count))
    else:
        utf8_bytes = text.encode('utf-8')
        if len(utf8_bytes) % 2 != 0:
            utf8_bytes += b'\x00'

        for i in range(0, len(utf8_bytes), 2):
            b1 = utf8_bytes[i]
            b2 = utf8_bytes[i+1]
            n1 = b1 >> 4
            n2 = b1 & 0x0F
            n3 = b2 >> 4
            n4 = b2 & 0x0F
            pua_code = PUA_START + (n1 << 12) + (n2 << 8) + (n3 << 4) + n4
            encoded_chars.append(chr(pua_code))

    separator = " " if add_space else ""
    return separator.join(encoded_chars)


PUA_START = 0xF0000

def decode_aijungeum(encoded_text: str, hex_mode: bool = False) -> str:
    clean_text = "".join(encoded_text.split())
    if not clean_text:
        return ""

    if hex_mode:
        if len(clean_text) < 2:
            return ""
        pad_count = ord(clean_text[-1]) - PUA_START
        data_chars = clean_text[:-1]

        hex_chunks = [f"{(ord(ch) - PUA_START):04X}" for ch in data_chars if PUA_START <= ord(ch) <= PUA_START + 0xFFFF]
        full_hex = "".join(hex_chunks)
        return full_hex[:-pad_count] if 0 < pad_count <= 3 else full_hex

    # 일반 텍스트(UTF-8) 디코딩
    decoded_bytes = bytearray()
    for ch in clean_text:
        offset = ord(ch) - PUA_START
        if 0 <= offset <= 0xFFFF:
            decoded_bytes.append((offset >> 8) & 0xFF)
            decoded_bytes.append(offset & 0xFF)

    # 맨 마지막 바이트가 패딩(0x00)인 경우 딱 1바이트만 제거
    if decoded_bytes.endswith(b'\x00'):
        decoded_bytes = decoded_bytes[:-1]

    return decoded_bytes.decode('utf-8', errors='replace')


def pack_aijungeum(text: str, add_space: bool = False) -> str:
    """
    입력 스트링을 UTF-8 인코딩 후 zlib(최대 압축 level=9)으로 압축하고,
    압축된 바이너리(2바이트 단위)를 PUA 문자로 매핑.
    """
    # text > UTF-8 > zlib 최대 압축 (헤더/푸터 6바이트)
    raw_bytes = text.encode('utf-8')
    compressed_bytes = zlib.compress(raw_bytes, level=9)
    
    # 패딩: 2바이트 단위, 홀수 일때 0x00 패딩 1바이트 추가
    pad_byte_count = len(compressed_bytes) % 2
    if pad_byte_count == 1:
        compressed_bytes += b'\x00'
        
    encoded_chars = list()
    
    # 4개씩(2바이트) 읽어 PUA 코드포인트로 매핑
    for i in range(0, len(compressed_bytes), 2):
        b1 = compressed_bytes[i]
        b2 = compressed_bytes[i+1]
        
        n1 = b1 >> 4        # 2사분면
        n2 = b1 & 0x0F      # 1사분면
        n3 = b2 >> 4        # 3사분면
        n4 = b2 & 0x0F      # 4사분면 
        
        pua_code = PUA_START + (n1 << 12) + (n2 << 8) + (n3 << 4) + n4
        encoded_chars.append(chr(pua_code))
        
    # 패딩 카운트 기록: 맨 마지막 1글자(2바이트)에 패딩된 바이트 수(0 또는 1) 기록
    encoded_chars.append(chr(PUA_START + pad_byte_count))
    
    separator = " " if add_space else ""
    return separator.join(encoded_chars)


def unpack_aijungeum(encoded_text: str) -> str:
    """
    PUA 문자를 바이너리 바이트로 복원한 뒤, zlib 압축을 해제하여 원본 텍스트로 디코딩.
    """
    clean_text = "".join(encoded_text.split())
    if len(clean_text) < 2:
        return ""
        
    # 패딩 카운트 조회: 마지막 1글자(2바이트)에서 패딩 바이트 수(0 또는 1) 확인
    pad_byte_count = ord(clean_text[-1]) - PUA_START
    data_chars = clean_text[:-1]
    
    # PUA 문자를 다시 2바이트씩 바이너리로 복원
    compressed_bytes = bytearray()
    for ch in data_chars:
        offset = ord(ch) - PUA_START
        if 0 <= offset <= 0xFFFF:
            b1 = (offset >> 8) & 0xFF
            b2 = offset & 0xFF
            compressed_bytes.append(b1)
            compressed_bytes.append(b2)
            
    # 인코딩 시 추가되었던 1바이트 패딩 제거
    if pad_byte_count == 1:
        compressed_bytes = compressed_bytes[:-1]
        
    # zlib 압축 해제 후 UTF-8 텍스트로 디코딩
    decompressed_bytes = zlib.decompress(bytes(compressed_bytes))
    return decompressed_bytes.decode('utf-8', errors='replace')


if __name__ == "__main__":
    add_space = True        # add_space=True: pretty print 
    valid_modes = ("encode", "decode", "hex", "dehex", "pack", "unpack") 

    first_arg = "".join(sys.argv[1:2]).lower()
    if first_arg in valid_modes:
        mode = first_arg
        user_input = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
    else:
        mode = "auto"
        user_input = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "hello"

    # '\U000f6865' 형태의 이스케이프 문자열 자동 변환
    if "\\u" in user_input.lower():
        try:
            user_input = user_input.encode('utf-8').decode('unicode_escape')
        except Exception:
            pass

    print(f"입력값: {repr(user_input)}\n")

    clean_check = "".join(user_input.split())
    is_pua = bool(clean_check) and all(PUA_START <= ord(c) <= 0xFFFFD for c in clean_check)

    if mode == "pack":
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
        codes_text = " ".join(f"U+{ord(c):05X}" for c in enc_text.split())
        print(f"[hex_mode=True] 변환 결과 : {enc_text}")
        print(f"[hex_mode=True] 코드포인트: {codes_text}")
        print(f"[hex_mode=True] 디코딩 복원: {decode_aijungeum(enc_text, hex_mode=True)}")
    else:
        enc_text = encode_aijungeum(user_input, add_space=add_space, hex_mode=False)
        codes_text = " ".join(f"U+{ord(c):05X}" for c in enc_text.split())
        print(f"[hex_mode=False] 변환 결과 : {enc_text}")
        print(f"[hex_mode=False] 코드포인트: {codes_text}")
        print(f"[hex_mode=False] 디코딩 복원: {decode_aijungeum(enc_text, hex_mode=False)}")

