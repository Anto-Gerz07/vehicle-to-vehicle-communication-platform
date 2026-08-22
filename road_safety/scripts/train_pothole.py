"""
scripts/train_pothole.py — Fine-tune YOLOv8-nano on a pothole detection dataset.

Dataset source: Mendeley Data — "An Annotated Water-Filled, and Dry Potholes Dataset"
  https://data.mendeley.com/datasets/tp95cdvgm8/1

Steps:
  1. Go to the URL above and download "Potholes.zip".
  2. Place "Potholes.zip" inside the "road_safety/datasets/" folder.
  3. Run: python scripts/train_pothole.py
  4. The fine-tuned weights will be saved to: models/pothole.pt

Training happens on the RTX 4060 (CUDA). Expect ~30–60 min for 50 epochs.
"""

import os
import shutil
import random
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
EPOCHS   = 50
IMGSZ    = 640
BATCH    = 16
DEVICE   = "cuda"   # or "cpu"

# Change to "yolov8n.pt" to start from scratch, or "models/pothole.pt" to resume
BASE_MODEL = "models/pothole.pt"

OUTPUT_MODEL = Path("models/pothole.pt")
DATASET_DIR  = Path("datasets/pothole").resolve()
YAML_PATH    = DATASET_DIR / "dataset.yaml"
ZIP_PATH     = Path("datasets/Potholes.zip")
# ---------------------------------------------------------------------------

def prepare_mendeley_dataset():
    """Extract Potholes.zip and format it for YOLOv8."""
    if not ZIP_PATH.exists():
        raise SystemExit(
            f"\n[!] Dataset missing!\n"
            f"Please download 'Potholes.zip' from:\n"
            f"  https://data.mendeley.com/datasets/tp95cdvgm8/1\n\n"
            f"And place it at: {ZIP_PATH.resolve()}\n"
            f"Then run this script again.\n"
        )
    
    print(f"[train_pothole] Extracting {ZIP_PATH}...")
    extract_dir = DATASET_DIR / "extracted"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True)
    
    with zipfile.ZipFile(ZIP_PATH, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
    
    # Mendeley dataset has IMG/ and TXT/ folders inside the zip
    img_dir = extract_dir / "IMG"
    txt_dir = extract_dir / "TXT"
    
    if not img_dir.exists() or not txt_dir.exists():
        # Sometimes they are nested in another folder inside the zip
        subdirs = list(extract_dir.iterdir())
        if len(subdirs) == 1 and subdirs[0].is_dir():
            img_dir = subdirs[0] / "IMG"
            txt_dir = subdirs[0] / "TXT"
    
    if not img_dir.exists() or not txt_dir.exists():
        raise RuntimeError(f"Could not find IMG/ and TXT/ folders inside {ZIP_PATH}")
    
    # Create YOLO directory structure
    for split in ["train", "val"]:
        (DATASET_DIR / "images" / split).mkdir(parents=True, exist_ok=True)
        (DATASET_DIR / "labels" / split).mkdir(parents=True, exist_ok=True)
    
    # Gather all images
    images = [f for f in img_dir.iterdir() if f.suffix.lower() in [".jpg", ".png", ".jpeg"]]
    random.shuffle(images)
    
    split_idx = int(len(images) * 0.8) # 80/20 split
    train_imgs = images[:split_idx]
    val_imgs   = images[split_idx:]
    
    print(f"[train_pothole] Formatting {len(images)} images (80/20 split)...")
    
    def move_files(img_list, split_name):
        for img_path in img_list:
            txt_path = txt_dir / (img_path.stem + ".txt")
            if not txt_path.exists():
                continue # Skip if no label exists
            
            shutil.copy(img_path, DATASET_DIR / "images" / split_name / img_path.name)
            shutil.copy(txt_path, DATASET_DIR / "labels" / split_name / txt_path.name)

    move_files(train_imgs, "train")
    move_files(val_imgs, "val")
    
    # Clean up extraction temp folder
    shutil.rmtree(extract_dir)

    # Create YOLOv8 dataset.yaml
    yaml_content = f"""path: {DATASET_DIR}
train: images/train
val: images/val

names:
  0: pothole
"""
    YAML_PATH.write_text(yaml_content)
    print(f"[train_pothole] Created YOLOv8 dataset at {DATASET_DIR}")
    return str(YAML_PATH)


def train(data_yaml: str):
    """Fine-tune YOLOv8n on the pothole dataset."""
    try:
        from ultralytics import YOLO
    except ImportError:
        raise SystemExit("ultralytics package not installed. Run: pip install ultralytics")

    OUTPUT_MODEL.parent.mkdir(parents=True, exist_ok=True)

    print(f"[train_pothole] Starting training — {EPOCHS} epochs, imgsz={IMGSZ}")
    
    # Fallback to yolov8n.pt if the base model isn't found (e.g. first run)
    actual_base = BASE_MODEL if Path(BASE_MODEL).exists() else "yolov8n.pt"
    print(f"[train_pothole] Using base model: {actual_base}")
    
    model = YOLO(actual_base)
    results = model.train(
        data    = data_yaml,
        epochs  = EPOCHS,
        imgsz   = IMGSZ,
        batch   = BATCH,
        device  = DEVICE,
        project = str(Path("datasets/pothole_runs").resolve()),
        name    = "pothole_v1",
        exist_ok= True,
    )

    # Copy best weights to models/pothole.pt
    best = Path("datasets/pothole_runs/pothole_v1/weights/best.pt")
    if best.exists():
        shutil.copy(best, OUTPUT_MODEL)
        print(f"[train_pothole] ✓ Best weights saved to: {OUTPUT_MODEL}")
    else:
        print(f"[train_pothole] WARNING: best.pt not found at {best}")


def main():
    print("=" * 60)
    print("  Pothole Detector — Training Script (Mendeley)")
    print("=" * 60)

    if YAML_PATH.exists():
        print(f"[train_pothole] Using existing dataset YAML: {YAML_PATH}")
        data_yaml = str(YAML_PATH)
    else:
        data_yaml = prepare_mendeley_dataset()

    train(data_yaml)


if __name__ == "__main__":
    main()
