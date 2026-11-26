import os
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, random_split

# dataset_generator_aijungeum
from dataset_generator_aijungeum import (
    AiJungEumDataset,
    preds_to_bytes,
    preds_to_pua,
    OUTPUT_PT_PATH
)

# ==============================================================================
# device selector
# ==============================================================================
def get_best_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


# ==============================================================================
# 경량 4-Head CNN 합성곱 신경망 모델 정의 (48x48 흑백 입력 -> 4가지 구성 요소(초성1, 초성2, 종성1, 종성2)를 각각 16가지 후보(0~15) 중 하나로 동시에 분류)
# ==============================================================================
class AiJungEumNet(nn.Module):
    def __init__(self):
        super().__init__()
        # 공간 위치(상하좌우 4분할 구조)를 유지하면서 특징을 추출하는 백본
        self.features = nn.Sequential(
            # Block 1: (1, 48, 48) -> (32, 24, 24)
            nn.Conv2d(1, 32, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),

            # Block 2: (32, 24, 24) -> (64, 12, 12)
            nn.Conv2d(32, 64, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),

            # Block 3: (64, 12, 12) -> (128, 6, 6)
            nn.Conv2d(64, 128, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),

            # Block 4: (128, 6, 6) -> (256, 3, 3)
            nn.Conv2d(128, 256, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2)
        )

        # 위치 정보를 잃지 않기 위해 Global Average Pooling 대신 Flatten 사용 (256 * 3 * 3 = 2304)
        self.shared_fc = nn.Sequential(
            nn.Flatten(),
            nn.Linear(256 * 3 * 3, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(inplace=True),
            nn.Dropout(0.2)
        )

        # 4개의 독립된 분류 헤드 (각 헤드가 0~15 중 하나를 예측)
        self.head1 = nn.Linear(512, 16)  # 초성1 (상위 4비트)
        self.head2 = nn.Linear(512, 16)  # 초성2
        self.head3 = nn.Linear(512, 16)  # 종성1
        self.head4 = nn.Linear(512, 16)  # 종성2 (하위 4비트)

    def forward(self, x):
        feat = self.features(x)
        shared = self.shared_fc(feat)
        return (
            self.head1(shared),
            self.head2(shared),
            self.head3(shared),
            self.head4(shared)
        )


# ==============================================================================
# 학습 및 검증 루프
# ==============================================================================
def train_model(
    pt_path: str = OUTPUT_PT_PATH,
    save_model_path: str = "aijungeum_best_model.pth",
    batch_size: int = 256,
    epochs: int = 15,
    lr: float = 1e-3
):
    device = get_best_device()
    print(f"학습 장치: {device}")

    if not os.path.exists(pt_path):
        raise FileNotFoundError(f"데이터셋 파일이 없습니다: {pt_path}. 먼저 생성기를 실행하세요.")

    # CUDA 환경일 때만 pin_memory 및 멀티 워커 활성화 (macOS MPS 경고 및 오버헤드 방지)
    use_pin_memory = (device.type == "cuda")
    workers = 2 if device.type == "cuda" else 0

    # 데이터셋 로드 및 90% 학습 / 10% 검증 분할
    full_dataset = AiJungEumDataset(pt_path)
    train_size = int(len(full_dataset) * 0.9)
    val_size = len(full_dataset) - train_size
    train_dataset, val_dataset = random_split(full_dataset, [train_size, val_size])

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=workers,
        pin_memory=use_pin_memory
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=workers,
        pin_memory=use_pin_memory
    )

    model = AiJungEumNet().to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    best_exact_acc = 0.0

    for epoch in range(1, epochs + 1):
        # --- [학습 단계] ---
        model.train()
        running_loss = 0.0

        for imgs, targets in train_loader:
            imgs = imgs.to(device)
            targets = targets.to(device)  # Shape: (B, 4)

            optimizer.zero_grad()
            out1, out2, out3, out4 = model(imgs)

            # 4개 헤드의 손실(Loss)을 모두 합산하여 역전파
            loss = (
                criterion(out1, targets[:, 0]) +
                criterion(out2, targets[:, 1]) +
                criterion(out3, targets[:, 2]) +
                criterion(out4, targets[:, 3])
            )
            loss.backward()
            optimizer.step()

            running_loss += loss.item() * imgs.size(0)

        scheduler.step()
        train_loss = running_loss / train_size

        # --- [검증 단계] ---
        model.eval()
        total_samples = 0
        exact_match_count = 0  # 4자음이 모두 맞아 2바이트가 완벽히 복원된 개수
        char_match_count = 0   # 개별 자음 단위 정답 개수

        with torch.no_grad():
            for imgs, targets in val_loader:
                imgs = imgs.to(device)
                targets = targets.to(device)

                out1, out2, out3, out4 = model(imgs)

                # 각 헤드별 최댓값 인덱스 추출 -> (B, 4) 형태로 결합
                preds = torch.stack([
                    out1.argmax(dim=1),
                    out2.argmax(dim=1),
                    out3.argmax(dim=1),
                    out4.argmax(dim=1)
                ], dim=1)

                matches = (preds == targets)
                char_match_count += matches.sum().item()
                # 4개 자음이 모두 True인 경우만 카운트 (16비트 완전 복원 성공)
                exact_match_count += matches.all(dim=1).sum().item()
                total_samples += imgs.size(0)

        char_acc = (char_match_count / (total_samples * 4)) * 100
        exact_acc = (exact_match_count / total_samples) * 100

        print(
            f"[Epoch {epoch:02d}/{epochs:02d}] "
            f"Loss: {train_loss:.4f} | "
            f"자음 정확도: {char_acc:.2f}% | "
            f"2바이트 완전일치율: {exact_acc:.2f}%"
        )

        # 과적합 방지: 신기록 갱신 
        if exact_acc >= best_exact_acc:
            best_exact_acc = exact_acc
            torch.save(model.state_dict(), save_model_path)

    print(f"\n학습 완료. 2바이트 전체 일치 확율 : {best_exact_acc:.2f}% (저장: {save_model_path})")


# ==============================================================================
# 학습된 모델로 실제 추론 및 바이너리 복원 테스트
# ==============================================================================
def test_inference(model_path: str = "aijungeum_best_model.pth", pt_path: str = OUTPUT_PT_PATH):
    device = get_best_device()

    model = AiJungEumNet().to(device)
    model.load_state_dict(torch.load(model_path, map_location=device, weights_only=True))
    model.eval()

    dataset = AiJungEumDataset(pt_path)
        # 점프 경계값인 0x8000 부근 샘플 테스트
    sample_idx = 0x8005 * 2 if len(dataset) > 0x8005 * 2 else 0 
    img, target = dataset[sample_idx]

    with torch.no_grad():
        input_tensor = img.unsqueeze(0).to(device)  # (1, 1, 48, 48)
        out1, out2, out3, out4 = model(input_tensor)
        pred_c = [
            out1.argmax(dim=1).item(),
            out2.argmax(dim=1).item(),
            out3.argmax(dim=1).item(),
            out4.argmax(dim=1).item()
        ]

    true_c = target.tolist()
    pred_bytes = preds_to_bytes(*pred_c)
    pred_pua = preds_to_pua(*pred_c)

    print("\n--- [추론 및 바이너리 복원 테스트] ---")
    print(f"실제 정답 (4자음): {true_c}")
    print(f"모델 예측 (4자음): {pred_c}")
    print(f"복원된 2바이트   : {pred_bytes} (Hex: {pred_bytes.hex().upper()})")
    print(f"복원된 PUA 문자  : {pred_pua} (U+{ord(pred_pua):05X})")


if __name__ == "__main__":
    train_model(
        pt_path=OUTPUT_PT_PATH,
        save_model_path="aijungeum_best_model.pth",
        batch_size=256,
        epochs=15,
        lr=1e-3
    )
    test_inference()
