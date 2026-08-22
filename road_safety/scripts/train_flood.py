"""
scripts/train_flood.py — Fine-tune MobileNetV2 as a binary road-flood classifier.

Dataset:
  This script uses 'datasets/flood.zip' (441 annotated roadway flooding images)
  for the FLOODED class.
  For NORMAL (dry road) images, it scrapes Bing if they are not already present.

Steps:
  1. Run: python scripts/train_flood.py
  2. Trained weights saved to: models/flood.pth
"""

import os
import sys
import copy
import shutil
import random
import zipfile
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# ---------------------------------------------------------------------------
DATASET_DIR     = Path("datasets/flood").resolve()
FLOOD_ZIP       = Path("datasets/flood.zip").resolve()
YOLO_FLOOD_ZIP  = Path("datasets/floods.v1i.yolov8.zip").resolve()
OUTPUT_MODEL    = Path("models/flood.pth")

EPOCHS          = 25
BATCH_SIZE      = 32
LR_HEAD         = 1e-3    # Classifier head LR
LR_BODY         = 1e-4    # Unfrozen backbone LR (fine-tuning)
DEVICE_STR      = "cuda"
IMGSZ           = config.FLOOD_INPUT_SIZE
TARGET_NORMAL   = 441     # Match the number of flooded images
# ---------------------------------------------------------------------------


def extract_flooded_images():
    """Extract flooded road images from flood.zip (441 annotated images)."""
    flooded_dir = DATASET_DIR / "_raw" / "flooded"
    flooded_dir.mkdir(parents=True, exist_ok=True)

    if len(list(flooded_dir.glob("*.*"))) >= 100:
        print(f"[train_flood] Flooded images already extracted ({len(list(flooded_dir.glob('*.*')))} found).")
        return flooded_dir

    if FLOOD_ZIP.exists():
        print(f"[train_flood] Extracting {FLOOD_ZIP.name} ({441} roadway flooding images)...")
        with zipfile.ZipFile(FLOOD_ZIP, 'r') as z:
            for info in z.infolist():
                # Only extract images, not label masks
                if info.filename.startswith("Dataset/images/") and not info.filename.endswith("/"):
                    data = z.read(info.filename)
                    fname = Path(info.filename).name
                    (flooded_dir / fname).write_bytes(data)
        print(f"[train_flood] ✓ Extracted {len(list(flooded_dir.glob('*.*')))} flooded images.")

    # Also grab images from the Roboflow YOLO zip (more variety)
    if YOLO_FLOOD_ZIP.exists():
        print(f"[train_flood] Also extracting images from {YOLO_FLOOD_ZIP.name}...")
        with zipfile.ZipFile(YOLO_FLOOD_ZIP, 'r') as z:
            for info in z.infolist():
                if "images" in info.filename and info.filename.lower().endswith((".jpg", ".jpeg", ".png")):
                    data = z.read(info.filename)
                    fname = "rf_" + Path(info.filename).name
                    (flooded_dir / fname).write_bytes(data)
        print(f"[train_flood] ✓ Total flooded images: {len(list(flooded_dir.glob('*.*')))}")

    return flooded_dir


def get_normal_images():
    """Get or scrape normal dry road images."""
    normal_dir = DATASET_DIR / "_raw" / "normal"
    normal_dir.mkdir(parents=True, exist_ok=True)

    existing = list(normal_dir.glob("*.*"))
    if len(existing) >= 80:
        print(f"[train_flood] Normal images already present ({len(existing)} found).")
        return normal_dir

    print(f"\n[train_flood] Scraping {TARGET_NORMAL} dry road images (this is a one-time step)...")
    try:
        from bing_image_downloader import downloader
    except ImportError:
        raise SystemExit("Run: pip install bing-image-downloader")

    scrape_dir = DATASET_DIR / "_scrape"
    queries = [
        ("dry road highway asphalt", 150),
        ("empty street road daytime", 100),
        ("wet road after rain no flood", 100),
        ("road highway driving perspective", 91),
    ]

    for query, limit in queries:
        print(f"  Scraping: '{query}' ({limit} images)...")
        downloader.download(
            query, limit=limit,
            output_dir=str(scrape_dir),
            force_replace=False, timeout=8, verbose=False
        )
        for img in (scrape_dir / query).glob("*.*"):
            shutil.move(str(img), normal_dir / (query[:10].replace(" ", "_") + "_" + img.name))
        try:
            (scrape_dir / query).rmdir()
        except Exception:
            pass

    shutil.rmtree(scrape_dir, ignore_errors=True)
    print(f"[train_flood] ✓ Got {len(list(normal_dir.glob('*.*')))} normal road images.")
    return normal_dir


def build_splits(flooded_dir: Path, normal_dir: Path):
    """Organize raw images into train/val splits."""
    print("\n[train_flood] Building train/val splits (80/20)...")

    for split in ["train", "val"]:
        for cls in ["flooded", "normal"]:
            (DATASET_DIR / split / cls).mkdir(parents=True, exist_ok=True)
            # Clean existing
            for f in (DATASET_DIR / split / cls).glob("*.*"):
                f.unlink()

    def split_and_copy(src_dir, class_name):
        imgs = [f for f in src_dir.glob("*.*") if f.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]]
        random.shuffle(imgs)
        split_idx = int(len(imgs) * 0.8)
        for img in imgs[:split_idx]:
            shutil.copy(img, DATASET_DIR / "train" / class_name / img.name)
        for img in imgs[split_idx:]:
            shutil.copy(img, DATASET_DIR / "val" / class_name / img.name)
        return len(imgs[:split_idx]), len(imgs[split_idx:])

    f_train, f_val = split_and_copy(flooded_dir, "flooded")
    n_train, n_val = split_and_copy(normal_dir, "normal")

    print(f"  Train — flooded: {f_train}, normal: {n_train}")
    print(f"  Val   — flooded: {f_val},  normal: {n_val}")


def build_dataloaders():
    try:
        import torch
        from torchvision import datasets, transforms
        from torch.utils.data import DataLoader
    except ImportError:
        raise SystemExit("Run: pip install torch torchvision")

    # Check if splits exist with enough data
    train_dir = DATASET_DIR / "train"
    val_dir   = DATASET_DIR / "val"
    needs_rebuild = (
        not train_dir.exists() or
        len(list((train_dir / "flooded").glob("*.*"))) < 50
    )

    if needs_rebuild:
        flooded_dir = extract_flooded_images()
        normal_dir  = get_normal_images()
        build_splits(flooded_dir, normal_dir)

    train_tf = transforms.Compose([
        transforms.Resize((IMGSZ + 32, IMGSZ + 32)),
        transforms.RandomCrop(IMGSZ),
        transforms.RandomHorizontalFlip(),
        transforms.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.2, hue=0.05),
        transforms.RandomRotation(10),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    val_tf = transforms.Compose([
        transforms.Resize((IMGSZ, IMGSZ)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    train_ds = datasets.ImageFolder(str(train_dir), transform=train_tf)
    val_ds   = datasets.ImageFolder(str(val_dir),   transform=val_tf)

    print(f"\n[train_flood] Classes: {train_ds.classes}")
    print(f"[train_flood] Train: {len(train_ds)} | Val: {len(val_ds)}")

    train_dl = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True,  num_workers=4, pin_memory=True)
    val_dl   = DataLoader(val_ds,   batch_size=BATCH_SIZE, shuffle=False, num_workers=4, pin_memory=True)
    return train_dl, val_dl


def build_model(device):
    import torch.nn as nn
    from torchvision import models

    model = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.IMAGENET1K_V1)
    # Replace head for binary classification
    in_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(in_features, 2)

    # Freeze all layers first
    for param in model.parameters():
        param.requires_grad = False

    # Unfreeze the last 3 feature blocks + classifier for fine-tuning
    for layer in list(model.features.children())[-3:]:
        for param in layer.parameters():
            param.requires_grad = True
    for param in model.classifier.parameters():
        param.requires_grad = True

    model.to(device)
    return model


def train():
    import torch
    import torch.nn as nn
    import torch.optim as optim

    device = torch.device(DEVICE_STR if torch.cuda.is_available() else "cpu")
    print(f"[train_flood] Using device: {device}")

    train_dl, val_dl = build_dataloaders()
    model = build_model(device)

    criterion = nn.CrossEntropyLoss()

    # Separate LR for head vs backbone layers
    backbone_params = [p for p in model.features.parameters() if p.requires_grad]
    head_params     = list(model.classifier.parameters())
    optimizer = optim.Adam([
        {"params": backbone_params, "lr": LR_BODY},
        {"params": head_params,     "lr": LR_HEAD},
    ])
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)

    best_acc   = 0.0
    best_state = None

    for epoch in range(1, EPOCHS + 1):
        model.train()
        running_loss = correct = total = 0

        for imgs, labels in train_dl:
            imgs, labels = imgs.to(device), labels.to(device)
            optimizer.zero_grad()
            loss = criterion(model(imgs), labels)
            loss.backward()
            optimizer.step()
            running_loss += loss.item() * imgs.size(0)
            _, preds = model(imgs).max(1)
            correct += preds.eq(labels).sum().item()
            total   += labels.size(0)

        train_acc  = correct / total
        train_loss = running_loss / total

        model.eval()
        val_correct = val_total = 0
        with torch.no_grad():
            for imgs, labels in val_dl:
                imgs, labels = imgs.to(device), labels.to(device)
                _, preds = model(imgs).max(1)
                val_correct += preds.eq(labels).sum().item()
                val_total   += labels.size(0)

        val_acc = val_correct / val_total
        scheduler.step()

        marker = "  ✓ New best!" if val_acc > best_acc else ""
        print(f"Epoch [{epoch:02d}/{EPOCHS}]  Loss: {train_loss:.4f}  Train: {train_acc:.3f}  Val: {val_acc:.3f}{marker}")

        if val_acc > best_acc:
            best_acc   = val_acc
            best_state = copy.deepcopy(model.state_dict())

    OUTPUT_MODEL.parent.mkdir(parents=True, exist_ok=True)
    torch.save(best_state, str(OUTPUT_MODEL))
    print(f"\n[train_flood] ✓ Best model saved → {OUTPUT_MODEL}  (val acc={best_acc:.3f})")


if __name__ == "__main__":
    print("=" * 60)
    print("  Flood Classifier — Training Script (v2)")
    print("=" * 60)
    train()
