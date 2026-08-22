"""
scripts/train_flood.py — Fine-tune MobileNetV2 as a binary road-flood classifier.

Dataset source: 
  This script can auto-generate a dataset by scraping images of flooded and dry roads.
  Or, you can use Roboflow Universe ("Flood Classification").

Steps:
  1. Run: python scripts/train_flood.py
  2. If the dataset folder is missing, the script will automatically download images for you.
  3. Trained weights saved to: models/flood.pth

Training on RTX 4060 — expect ~5 min for 20 epochs on ~300 images.
"""

import os
import sys
import copy
import shutil
import random
from pathlib import Path

# Add the parent directory to sys.path so we can import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ROBOFLOW_API_KEY   = os.getenv("ROBOFLOW_API_KEY", "YOUR_API_KEY_HERE")
ROBOFLOW_WORKSPACE = "WORKSPACE_NAME_HERE"
ROBOFLOW_PROJECT   = "PROJECT_NAME_HERE"

DATASET_DIR   = Path("datasets/flood").resolve()
OUTPUT_MODEL  = Path("models/flood.pth")
EPOCHS        = 20
BATCH_SIZE    = 32
LR            = 1e-3
DEVICE_STR    = "cuda"   # or "cpu"
IMGSZ         = config.FLOOD_INPUT_SIZE
# ---------------------------------------------------------------------------

def auto_build_dataset():
    """Automatically build a dataset by scraping images if Roboflow isn't provided."""
    try:
        from bing_image_downloader import downloader
    except ImportError:
        raise SystemExit(
            "\n[!] Dataset missing and scraper not installed.\n"
            "Run: pip install bing-image-downloader\n"
            "Then run this script again."
        )

    print("\n[train_flood] No Roboflow dataset provided.")
    print("[train_flood] Automatically scraping images to build a custom dataset...\n")

    scrape_dir = DATASET_DIR / "scraped"
    
    # Download 150 images for each class
    for query, class_name in [("flooded road", "flooded"), ("empty dry asphalt road", "normal")]:
        print(f"[train_flood] Scraping images for: {class_name}...")
        downloader.download(query, limit=150, output_dir=str(scrape_dir), force_replace=False, timeout=10, verbose=False)
        
        # Rename the folder downloaded by bing to our class name
        downloaded_folder = scrape_dir / query
        target_folder     = scrape_dir / class_name
        if downloaded_folder.exists() and not target_folder.exists():
            downloaded_folder.rename(target_folder)

    # Move files into train (80%) and val (20%) splits
    for split in ["train", "val"]:
        (DATASET_DIR / split / "flooded").mkdir(parents=True, exist_ok=True)
        (DATASET_DIR / split / "normal").mkdir(parents=True, exist_ok=True)

    for class_name in ["flooded", "normal"]:
        images = list((scrape_dir / class_name).glob("*.*"))
        random.shuffle(images)
        split_idx = int(len(images) * 0.8)
        
        for img in images[:split_idx]:
            shutil.move(str(img), DATASET_DIR / "train" / class_name / img.name)
        for img in images[split_idx:]:
            shutil.move(str(img), DATASET_DIR / "val" / class_name / img.name)

    shutil.rmtree(scrape_dir)
    print(f"\n[train_flood] ✓ Dataset successfully built at {DATASET_DIR}")
    return DATASET_DIR

def download_dataset():
    """Download the dataset from Roboflow in Folder format."""
    try:
        from roboflow import Roboflow
    except ImportError:
        raise SystemExit("Run: pip install roboflow")

    if ROBOFLOW_WORKSPACE == "WORKSPACE_NAME_HERE":
        return auto_build_dataset()

    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    rf = Roboflow(api_key=ROBOFLOW_API_KEY)
    
    try:
        project = rf.workspace(ROBOFLOW_WORKSPACE).project(ROBOFLOW_PROJECT)
        versions = project.versions()
        latest_version = max([v.version for v in versions])
        version = project.version(latest_version)
        dataset = version.download("folder", location=str(DATASET_DIR))
        return Path(dataset.location)
    except Exception as e:
        print(f"\nRoboflow Download Error:\n{e}\n")
        raise SystemExit(1)


def build_dataloaders():
    try:
        import torch
        from torchvision import datasets, transforms
        from torch.utils.data import DataLoader
    except ImportError:
        raise SystemExit("Run: pip install torch torchvision")

    dataset_path = DATASET_DIR
    if (DATASET_DIR / "train").exists():
        dataset_path = DATASET_DIR
    elif list(DATASET_DIR.glob("*/train")):
        dataset_path = list(DATASET_DIR.glob("*/train"))[0].parent
    else:
        dataset_path = download_dataset()

    train_tf = transforms.Compose([
        transforms.Resize((IMGSZ, IMGSZ)),
        transforms.RandomHorizontalFlip(),
        transforms.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.2),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    val_tf = transforms.Compose([
        transforms.Resize((IMGSZ, IMGSZ)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    train_dir = dataset_path / "train"
    val_dir   = dataset_path / "val"
    if not val_dir.exists():
        if (dataset_path / "valid").exists():
            val_dir = dataset_path / "valid"
        else:
            print("[train_flood] WARNING: No 'val' folder found. Using 'train' data for validation.")
            val_dir = train_dir


    train_ds = datasets.ImageFolder(str(train_dir), transform=train_tf)
    val_ds   = datasets.ImageFolder(str(val_dir),   transform=val_tf)

    print(f"[train_flood] Classes: {train_ds.classes}")
    print(f"[train_flood] Train samples: {len(train_ds)} | Val samples: {len(val_ds)}")

    train_dl = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True,  num_workers=4, pin_memory=True)
    val_dl   = DataLoader(val_ds,   batch_size=BATCH_SIZE, shuffle=False, num_workers=4, pin_memory=True)

    return train_dl, val_dl


def build_model(device):
    try:
        import torch.nn as nn
        from torchvision import models
    except ImportError:
        raise SystemExit("Run: pip install torch torchvision")

    model = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.IMAGENET1K_V1)
    # Freeze all layers first, then fine-tune the classifier
    for param in model.parameters():
        param.requires_grad = False
    in_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(in_features, 2)
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
    # Only train the classifier head initially
    optimizer = optim.Adam(model.classifier.parameters(), lr=LR)
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=7, gamma=0.1)

    best_acc   = 0.0
    best_state = None

    for epoch in range(1, EPOCHS + 1):
        # --- Training phase ---
        model.train()
        running_loss = 0.0
        correct = total = 0

        for imgs, labels in train_dl:
            imgs, labels = imgs.to(device), labels.to(device)
            optimizer.zero_grad()
            outputs = model(imgs)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            running_loss += loss.item() * imgs.size(0)
            _, preds = outputs.max(1)
            correct  += preds.eq(labels).sum().item()
            total    += labels.size(0)

        train_acc  = correct / total
        train_loss = running_loss / total

        # --- Validation phase ---
        model.eval()
        val_correct = val_total = 0
        with torch.no_grad():
            for imgs, labels in val_dl:
                imgs, labels = imgs.to(device), labels.to(device)
                outputs = model(imgs)
                _, preds = outputs.max(1)
                val_correct += preds.eq(labels).sum().item()
                val_total   += labels.size(0)

        val_acc = val_correct / val_total
        scheduler.step()

        print(
            f"Epoch [{epoch:02d}/{EPOCHS}]  "
            f"Loss: {train_loss:.4f}  "
            f"Train Acc: {train_acc:.3f}  "
            f"Val Acc: {val_acc:.3f}"
        )

        if val_acc > best_acc:
            best_acc   = val_acc
            best_state = copy.deepcopy(model.state_dict())
            print(f"  ✓ New best val acc: {best_acc:.3f}")

    # Save best weights
    OUTPUT_MODEL.parent.mkdir(parents=True, exist_ok=True)
    torch.save(best_state, str(OUTPUT_MODEL))
    print(f"\n[train_flood] ✓ Best model saved to: {OUTPUT_MODEL}  (val acc={best_acc:.3f})")


if __name__ == "__main__":
    print("=" * 60)
    print("  Flood Classifier — Training Script")
    print("=" * 60)
    train()
