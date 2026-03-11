---
license: cc-by-nc-nd-4.0
task_categories:
  - object-detection
  - image-classification
tags:
  - birds
  - bird-feeder
  - yolo
  - birdlense
  - wildlife
language:
  - en
size_categories:
  - n<1K
  - 1K<n<10K
  - 10K<n<100K
---

# BirdLense Annotations

Dataset of bird annotations from feeders for the [BirdLense Hub](https://github.com/Gfermoto/BirdLense-Hub) project — a bird feeder monitoring system with detection (YOLO, BirdNET).

## Description

Images of birds and squirrels captured by BirdLense cameras at feeders. Annotations in YOLO format (bounding boxes) for training and fine-tuning detection models. Data is collected by community members through confirming and correcting automatic detections.

## Dataset Structure

```
train/
  images/     # Training images
  labels/     # YOLO annotations (.txt)
val/
  images/
  labels/
data.yaml     # Class configuration and paths
```

## Classes

Species list is defined in `data.yaml`. Typical categories: birds (tits, sparrows, woodpeckers, etc.), squirrels, mice.

## Usage

### Download

```python
from huggingface_hub import snapshot_download

path = snapshot_download(
    repo_id="gfermoto/birdlense-annotations",
    repo_type="dataset",
    local_dir="./birdlense-data",
)
```

### YOLO Training

```bash
yolo detect train data=./birdlense-data/data.yaml model=yolov8n.pt epochs=100
```

## Data Source

- **BirdLense Hub** — open-source bird feeder monitoring system
- Detection: YOLO + BirdNET
- Labeling: user confirmation/correction in the UI

## License

[CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/) — attribution required, non-commercial, no derivatives without permission.

## Links

- [BirdLense Hub](https://github.com/Gfermoto/BirdLense-Hub)
- [BirdLense Documentation](https://github.com/Gfermoto/BirdLense-Hub/tree/main/docs)
