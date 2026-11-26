import os
import random
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ==============================================================================
# load font 
# ==============================================================================
FONT_PATH = "AiJungEum_0.1.a.ttc"  # font: AI정음 .ttc 
IMG_SIZE = 48                      # 48x48 px
FONT_SIZE = 38                     # 48x48 캔버스에 맞춘 폰트 크기
OUTPUT_PT_PATH = "aijungeum_48x48_dataset.pt"

# 검증: 데이터셋 생성 완료후 검증용 이미지 출력
ENABLE_VERIFY = True               # True: 샘플 추출 / False: skip 
VERIFY_OUTPUT_DIR = "verify_samples"

# AiJungEum 유니코드 영역 (중간 점프)
# PUA-A: U+F0000 ~ U+F7FFF (선형 주소 0x0000 ~ 0x7FFF)
# PUA-B: U+100000 ~ U+107FFF (선형 주소 0x8000 ~ 0xFFFF)
PUA_A_START = 0xF0000
PUA_B_START = 0x100000
JUMP_THRESHOLD = 0x8000


def offset_to_pua_char(offset: int) -> str:
    """16비트 선형 주소(0x0000~0xFFFF)를 점프 구간이 반영된 PUA-A/B 문자로 변환"""
    if offset < JUMP_THRESHOLD:
        return chr(PUA_A_START + offset)
    return chr(PUA_B_START + (offset & 0x7FFF))


def load_ttc_fonts(font_path: str, size: int) -> list[ImageFont.FreeTypeFont]:
    """
    .ttc 파일 내부에 포함된 모든 서브 폰트(index=0, 1, ...)를 순차 로드.
    """
    fonts = []
    index = 0
    while True:
        try:
            font = ImageFont.truetype(font_path, size=size, index=index)
            fonts.append(font)
            index += 1
        except OSError:
            break
    if not fonts:
        raise RuntimeError(f"font err: 폰트를 불러올 수 없습니다: {font_path}")
    print(f"로드된 .ttc 서브 폰트 개수: {len(fonts)}개 (index 0 ~ {len(fonts) - 1})")
    return fonts


def select_font_for_char(char: str, offset: int, fonts: list[ImageFont.FreeTypeFont]) -> ImageFont.FreeTypeFont:
    """
    해당 문자의 글리프가 실제로 들어있는 .ttc 서브 폰트 선택.
    """
    if len(fonts) == 1:
        return fonts[0]

    preferred_idx = 0 if offset < JUMP_THRESHOLD else 1
    candidate_indices = [preferred_idx] + [i for i in range(len(fonts)) if i != preferred_idx]

    for idx in candidate_indices:
        bbox = fonts[idx].getbbox(char)
        if bbox is not None and (bbox[2] - bbox[0]) > 0 and (bbox[3] - bbox[1]) > 0:
            return fonts[idx]

    return fonts[preferred_idx]


# ==============================================================================
# 데이터 증강 및 렌더링 (48x48 grayscale)
# ==============================================================================
def render_glyph(char: str, font: ImageFont.FreeTypeFont, augment: bool = False) -> np.ndarray:
    """
    PUA 1글자를 48x48 흑백(검은 배경=0, 흰 글자=255) numpy 배열로 렌더링.
    """
    img = Image.new("L", (IMG_SIZE, IMG_SIZE), color=255)
    draw = ImageDraw.Draw(img)

    bbox = draw.textbbox((0, 0), char, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (IMG_SIZE - text_w) // 2 - bbox[0]
    y = (IMG_SIZE - text_h) // 2 - bbox[1]

    if augment:
        x += random.randint(-2, 2)
        y += random.randint(-2, 2)

    draw.text((x, y), char, font=font, fill=0)

    if augment:
        angle = random.uniform(-3.0, 3.0)
        img = img.rotate(angle, resample=Image.Resampling.BILINEAR, fillcolor=255)

        if random.random() < 0.3:
            img = img.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.3, 0.7)))

    # 색상 반전 (배경=0, 글자획=255)
    arr = 255 - np.array(img, dtype=np.uint8)

    if augment:
        noise = np.random.normal(0, 8, arr.shape)
        arr = np.clip(arr.astype(np.float32) * random.uniform(0.8, 1.1) + noise, 0, 255).astype(np.uint8)

    return arr


# ==============================================================================
# 데이터셋 생성/저장 .pt 
# ==============================================================================
def generate_dataset_file(
    font_path: str = FONT_PATH,
    output_path: str = OUTPUT_PT_PATH,
    samples_per_class: int = 1,
    augment: bool = False
):
    if not os.path.exists(font_path):
        raise FileNotFoundError(f"폰트 파일을 찾을 수 없습니다: {font_path}")

    fonts = load_ttc_fonts(font_path, size=FONT_SIZE)

    total_codes = 65536
    total_samples = total_codes * samples_per_class

    images = np.zeros((total_samples, IMG_SIZE, IMG_SIZE), dtype=np.uint8)
    labels = np.zeros((total_samples,), dtype=np.uint16)

    idx = 0
    for offset in range(total_codes):
        char = offset_to_pua_char(offset)
        target_font = select_font_for_char(char, offset, fonts)

        for _ in range(samples_per_class):
            images[idx] = render_glyph(char, target_font, augment=augment)
            labels[idx] = offset
            idx += 1

        if (offset + 1) % 10000 == 0:
            print(f"진행률: {offset + 1} / {total_codes} 완료 (현재 코드포인트: U+{ord(char):05X})")

    data_dict = {
        "images": torch.from_numpy(images),  # Shape: (N, 48, 48), uint8
        "labels": torch.from_numpy(labels)   # Shape: (N,), uint16 (선형 0x0000~0xFFFF)
    }
    torch.save(data_dict, output_path)
    print(f"저장 완료: {output_path} (총 {total_samples}장)")

# ==============================================================================
#  Dataset (4-Head 정답 분리, 바이너리 복원)
# ==============================================================================
class AiJungEumDataset(Dataset):
    def __init__(self, pt_path: str):
        data = torch.load(pt_path, weights_only=True)
        self.images = data["images"]  # (N, 48, 48) uint8
        self.labels = data["labels"]  # (N,) uint16

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        img = self.images[idx].float().unsqueeze(0) / 255.0

        val = int(self.labels[idx].item())
        c1 = (val >> 12) & 0x0F
        c2 = (val >> 8)  & 0x0F
        c3 = (val >> 4)  & 0x0F
        c4 = val & 0x0F

        targets = torch.tensor([c1, c2, c3, c4], dtype=torch.long)
        return img, targets


# ==============================================================================
# 추론 -> 조립/복원: 선형 2바이트(bytes) 및 PUA 문자 변환 
# ==============================================================================
def preds_to_bytes(c1: int, c2: int, c3: int, c4: int) -> bytes:
    """4-Head 모델의 예측값(0~15 정수 4개)을 선형 2바이트 바이너리로 조립"""
    val = ((c1 & 0x0F) << 12) | ((c2 & 0x0F) << 8) | ((c3 & 0x0F) << 4) | (c4 & 0x0F)
    return val.to_bytes(2, byteorder="big")


def preds_to_pua(c1: int, c2: int, c3: int, c4: int) -> str:
    """4-Head 모델의 예측값(0~15 정수 4개)을 점프가 반영된 PUA 유니코드 1글자로 복원"""
    val = ((c1 & 0x0F) << 12) | ((c2 & 0x0F) << 8) | ((c3 & 0x0F) << 4) | (c4 & 0x0F)
    return offset_to_pua_char(val)


# ==============================================================================
# [검증 전용] 저장된 .pt에서 이미지와 정답을 꺼내 PNG로 내보내기 
# ==============================================================================
def export_verification_samples(
    pt_path: str = OUTPUT_PT_PATH,
    out_dir: str = VERIFY_OUTPUT_DIR,
    num_random: int = 10,
    white_background: bool = True
):
    """
    Sampling: 저장된 .pt 파일에서 무작위 샘플 꺼내 PNG로 저장.
    파일명: 선형 16진수, 4-Head 정답 정수, 유니코드 코드포인트 모두 기록. 
    """
    os.makedirs(out_dir, exist_ok=True)
    dataset = AiJungEumDataset(pt_path)
    total_len = len(dataset)
    samples_per_class = total_len // 65536

        # 필수 검증 경계값 (시작점, 점프 직전 0x7FFF, 점프 직후 0x8000, 끝점 0xFFFF)
    key_offsets = [0x0000, 0x0001, 0x1234, 0x7FFF, 0x8000, 0x8001, 0xFFFF]
    target_indices = [off * samples_per_class for off in key_offsets if off * samples_per_class < total_len]

    # 무작위 샘플 인덱스 추가
    random_indices = random.sample(range(total_len), min(num_random, total_len))
    check_indices = list(dict.fromkeys(target_indices + random_indices))

    print(f"\n[검증 모드 ON] '{out_dir}/' 폴더에 {len(check_indices)}장의 검증 이미지를 추출합니다...")

    for idx in check_indices:
        img_tensor, targets = dataset[idx]
        c1, c2, c3, c4 = targets.tolist()

        # 텐서(0.0~1.0) -> uint8(0~255) 복원
        arr = (img_tensor.squeeze(0).numpy() * 255.0).clip(0, 255).astype(np.uint8)
        # 흰 배경에 검은 글자로 재반전 (원본 학습 데이터는 검은 배경)
        if white_background:
            arr = 255 - arr

        val = (c1 << 12) | (c2 << 8) | (c3 << 4) | c4
        pua_char = offset_to_pua_char(val)
        cp_hex = f"U+{ord(pua_char):05X}"

        filename = f"idx_{idx:06d}_hex_{val:04X}_{cp_hex}_head_{c1}_{c2}_{c3}_{c4}.png"
        save_path = os.path.join(out_dir, filename)
        Image.fromarray(arr, mode="L").save(save_path)

    print(f"[검증 완료] '{out_dir}' 폴더의 PNG 파일명과 글자 모양이 일치하는지 확인하세요.")


# ==============================================================================
# 실행 및 .ttc 경계 검증 예시
# ==============================================================================
if __name__ == "__main__":
    # 데이터셋 생성: 폰트 기반 
    generate_dataset_file(
        font_path=FONT_PATH,
        output_path=OUTPUT_PT_PATH,
        samples_per_class=2,
        augment=True
    )

    # 완료후: 검증용으로 샘플 추출 (ENABLE_VERIFY가 True일 때만 동작) 
    if ENABLE_VERIFY:
        export_verification_samples(
            pt_path=OUTPUT_PT_PATH,
            out_dir=VERIFY_OUTPUT_DIR,
            num_random=10,
            white_background=True
        )

    # 파이토치 DataLoader 연동 테스트
    dataset = AiJungEumDataset(OUTPUT_PT_PATH)
    loader = DataLoader(dataset, batch_size=64, shuffle=True)

    sample_imgs, sample_targets = next(iter(loader))
    first_target = sample_targets[0].tolist()
    restored_bytes = preds_to_bytes(*first_target)
    restored_pua = preds_to_pua(*first_target)

    print(f"\n4-Head 정수 정답: {first_target}")
    print(f"복원된 선형 바이트: {restored_bytes} (Hex: {restored_bytes.hex().upper()})")
    print(f"복원된 PUA 코드 : U+{ord(restored_pua):05X}")


