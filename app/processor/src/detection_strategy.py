from abc import ABC, abstractmethod
import logging
from typing import List, Optional, Tuple
from dataclasses import dataclass
import numpy as np
from ultralytics import YOLO
import cv2

logger = logging.getLogger(__name__)

# Ultralytics YOLO COCO (80 classes): в режиме single-stage только «bird».
# Иначе cat/dog/лошадь попадали в БД как «виды» и размывали каталог наблюдений.
# Полный набор COCO — только при ``coco_animals_only_auto=False`` (см. настройки процессора).
_COCO_BIRD_ONLY_CLASS_NAMES = frozenset({'bird'})


def _track_maybe_retry(model, frame: np.ndarray, **kwargs):
    """ByteTrack иногда возвращает ``boxes.id is None`` на первом реальном кадре — повтор без нового кадра."""
    results = model.track(frame, **kwargs)
    if not results or len(results[0].boxes) == 0:
        return results
    if results[0].boxes.id is None:
        results = model.track(frame, **kwargs)
    return results


@dataclass
class DetectionResult:
    """Одна детекция: track_id, вид, confidence, bbox, crop (опционально)."""
    track_id: int
    class_name: str
    confidence: float
    bbox: List[float]
    blur_variance: Optional[float] = None
    crop: Optional[np.ndarray] = None

class DetectionStrategy(ABC):
    def __init__(self, min_center_dist: float = 0.1, min_box_size_px: int = 50, blur_threshold: float = 100.0, max_blur_checks: int = 3):
        self.min_center_dist = min_center_dist
        self.min_box_size_px = min_box_size_px
        self.blur_threshold = blur_threshold
        self.max_blur_checks = max_blur_checks

    def is_blurry(self, image: np.ndarray) -> Tuple[bool, float]:
        """Лапласиан: выше variance — резче. (is_blur, variance)."""
        if image is None or image.size == 0:
            return True, 0.0
        
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        variance = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        is_blur = variance < self.blur_threshold
        if is_blur:
            logger.info(f"Blur detected: variance={variance:.1f} < threshold={self.blur_threshold}")
        return is_blur, variance

    @abstractmethod
    def detect(self, frame: np.ndarray, tracker_config: str, min_confidence: float) -> List[DetectionResult]:
        pass
    
    @abstractmethod
    def reset(self):
        pass


    def is_valid_detection(self, bbox: List[float], conf: float, min_confidence: float) -> bool:
        """Центр не у краёв, confidence >= min."""
        x1, y1, x2, y2 = bbox
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        if (center_x < self.min_center_dist or center_x > (1 - self.min_center_dist) or
                center_y < self.min_center_dist or center_y > (1 - self.min_center_dist)):
            return False
        if conf < min_confidence:
            return False

        return True

class SingleStageStrategy(DetectionStrategy):
    def __init__(
        self,
        model_path: str,
        regional_species: Optional[List[str]] = None,
        min_center_dist: float = 0.1,
        coco_animals_only_auto: bool = True,
    ):
        super().__init__(min_center_dist)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.model = YOLO(model_path, task="detect")
        self.regional_species = regional_species
        self.classes = None

        if self.regional_species:
            self.logger.info(f'Initializing with regional species filters: {self.regional_species}')
            self.classes = [
                id
                for id, label in self.model.names.items()
                if any(reg_species in label for reg_species in self.regional_species)
            ]

            # Log the actual class names that are enabled
            enabled_classes = [self.model.names[id] for id in self.classes]
            self.logger.info(f'Regional species filters active: {len(self.classes)} classes enabled.')
            self.logger.info(f'Enabled classes: {enabled_classes}')
        elif coco_animals_only_auto:
            # yolov8n.pt (COCO): 80 classes — только птица, чтобы не писать в визиты млекопитающих.
            names = self.model.names
            if isinstance(names, dict) and len(names) == 80:
                bird_ids = [
                    cid
                    for cid, label in names.items()
                    if str(label).strip().lower() in _COCO_BIRD_ONLY_CLASS_NAMES
                ]
                if bird_ids:
                    self.classes = bird_ids
                    self.logger.info(
                        'Single-stage COCO (80 classes): detection limited to bird class only %s '
                        '(processor.single_stage_coco_animals_only_auto). '
                        'Set false for full COCO (not recommended for bird catalog).',
                        sorted(_COCO_BIRD_ONLY_CLASS_NAMES),
                    )

        # Warmup
        self.model.track(np.zeros((640, 640, 3)), tracker="bytetrack.yaml", persist=True, verbose=False)

    def detect(self, frame: np.ndarray, tracker_config: str, min_confidence: float) -> List[DetectionResult]:
        results = _track_maybe_retry(
            self.model,
            frame,
            persist=True,
            conf=min_confidence,
            classes=self.classes,
            tracker=tracker_config,
            verbose=False,
        )
        
        if not results or len(results[0].boxes) == 0:
            return []

        boxes = results[0].boxes
        # Without stable ByteTrack IDs, per-frame indexes create fake tracks.
        if boxes.id is None:
            return []
        track_ids = boxes.id.int().cpu().tolist()
        class_indexes = boxes.cls.int().cpu().tolist()
        confidences = boxes.conf.cpu().tolist()
        xyxyn = boxes.xyxyn.cpu().numpy()
        xyxy = boxes.xyxy.cpu().numpy()

        h, w, _ = frame.shape

        detection_results = []
        for track_id, class_idx, conf, bbox_norm, bbox_abs in zip(track_ids, class_indexes, confidences, xyxyn, xyxy):
            if not self.is_valid_detection(bbox_norm, conf, min_confidence):
                continue
            
            # Check min size
            x1n, y1n, x2n, y2n = bbox_norm
            if (x2n - x1n) * w < self.min_box_size_px or (y2n - y1n) * h < self.min_box_size_px:
                continue
            
            # Extract crop and compute blur
            x1, y1, x2, y2 = map(int, bbox_abs)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            
            if x2 <= x1 or y2 <= y1:
                continue
                
            crop = frame[y1:y2, x1:x2].copy()
            is_blur, blur_variance = self.is_blurry(crop)
            if is_blur:
                continue

            detection_results.append(DetectionResult(
                track_id=track_id, 
                class_name=self.model.names[class_idx], 
                confidence=conf, 
                bbox=bbox_norm,
                blur_variance=blur_variance,
                crop=crop
            ))
            
        return detection_results

    def reset(self):
        if hasattr(self.model.predictor, 'trackers'):
             self.model.predictor.trackers[0].reset()


class TwoStageStrategy(DetectionStrategy):
    def __init__(self, binary_model_path: str, classifier_model_path: str, regional_species: Optional[List[str]] = None, min_center_dist: float = 0.1, min_box_size_px: int = 50, blur_threshold: float = 100.0):
        super().__init__(min_center_dist, min_box_size_px, blur_threshold)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.regional_species = regional_species
        
        self.binary_model = YOLO(binary_model_path, task="detect")
        self.classifier_model = YOLO(classifier_model_path, task="classify")
        
        # Round-robin index for classification scheduling
        self._classification_index = 0
        
        # Pre-calculate allowed class IDs for regional species
        self.classes = None
        if self.regional_species:
            self.logger.info(f'Initializing with regional species filters: {self.regional_species}')
            self.classes = [
                id for id, label in self.classifier_model.names.items() 
                if any(reg_species in self._normalize_class_name(label) for reg_species in self.regional_species)
            ]
            # Log the actual class names that are enabled
            enabled_classes = [self._normalize_class_name(self.classifier_model.names[id]) for id in self.classes]
            self.logger.info(f'Regional species filters active: {len(self.classes)} classes enabled.')
            self.logger.info(f'Enabled classes: {enabled_classes}')

        # Warmup
        self.binary_model.track(np.zeros((320, 320, 3), dtype=np.uint8), tracker="bytetrack.yaml", persist=True, verbose=False)
        self.classifier_model(np.zeros((224, 224, 3), dtype=np.uint8), verbose=False)

    def _normalize_class_name(self, name: str) -> str:
        """Blue_Jay → Blue Jay, Winter_OR_juvenile → Winter/juvenile."""
        return name.replace('_OR_', '/').replace('_', ' ')

    def _classify_crop(self, crop: np.ndarray) -> Tuple[Optional[str], float]:
        """Классификация кропа. (species_name, confidence)."""
        result_cls = self.classifier_model(crop, verbose=False)
        
        if not result_cls or not result_cls[0].probs:
            return None, 0.0
            
        probs = result_cls[0].probs
        
        if self.classes:
            # Filter for best regional species
            all_probs = probs.data
            valid_probs = {cid: all_probs[cid].item() for cid in self.classes if cid < len(all_probs)}
            
            if valid_probs:
                best_id, best_conf = max(valid_probs.items(), key=lambda x: x[1])
                return self._normalize_class_name(result_cls[0].names[best_id]), best_conf
            return "Unknown", 0.0
            
        top1_idx = probs.top1
        return self._normalize_class_name(result_cls[0].names[top1_idx]), probs.top1conf.item()

    def detect(self, frame: np.ndarray, tracker_config: str, min_confidence: float) -> List[DetectionResult]:
        """Binary detect → фильтр валидности → round-robin классификация одного бокса на кадр."""
        results = _track_maybe_retry(
            self.binary_model,
            frame,
            persist=True,
            conf=min_confidence,
            verbose=False,
            imgsz=320,
            tracker=tracker_config,
        )
            
        if not results or len(results[0].boxes) == 0:
            return []

        boxes = results[0].boxes
        # Without stable ByteTrack IDs, per-frame indexes create fake tracks.
        if boxes.id is None:
            return []
        track_ids = boxes.id.int().cpu().tolist()
        confidences = boxes.conf.cpu().tolist()
        xyxyn = boxes.xyxyn.cpu().numpy() # normalized for output
        xyxy = boxes.xyxy.cpu().numpy()   # absolute for cropping

        h, w, _ = frame.shape

        valid_boxes = []
        for track_id, conf, bbox_norm, bbox_abs in zip(track_ids, confidences, xyxyn, xyxy):
            if not self.is_valid_detection(bbox_norm, conf, min_confidence):
                continue

            x1, y1, x2, y2 = map(int, bbox_abs)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
             
            if x2 <= x1 or y2 <= y1:
                continue
            box_w = x2 - x1
            box_h = y2 - y1
            if box_w < self.min_box_size_px or box_h < self.min_box_size_px:
                continue
            
            valid_boxes.append({
                'track_id': track_id,
                'conf': conf,
                'bbox_norm': bbox_norm,
                'crop_coords': (x1, y1, x2, y2)
            })
        
        if not valid_boxes:
            return []
        valid_boxes.sort(key=lambda b: b['track_id'])
        start_idx = self._classification_index % len(valid_boxes)
        self._classification_index += 1
        
        classified = None  # {track_id, crop, blur_variance}
        for i in range(min(len(valid_boxes), self.max_blur_checks)):
            idx = (start_idx + i) % len(valid_boxes)
            box = valid_boxes[idx]
            x1, y1, x2, y2 = box['crop_coords']
            crop = frame[y1:y2, x1:x2]
            is_blur, variance = self.is_blurry(crop)
            if not is_blur:
                classified = {
                    'track_id': box['track_id'],
                    'crop': crop.copy(),
                    'blur_variance': variance
                }
                break
        if classified is None and valid_boxes:
            box = valid_boxes[start_idx % len(valid_boxes)]
            x1, y1, x2, y2 = box['crop_coords']
            crop = frame[y1:y2, x1:x2]
            _, variance = self.is_blurry(crop)
            classified = {
                'track_id': box['track_id'],
                'crop': crop.copy(),
                'blur_variance': variance
            }
        detection_results = []
        for box in valid_boxes:
            species_name = None
            crop = None
            blur_variance = None
            combined_conf = box['conf']  # Default to detector confidence
            
            if classified and box['track_id'] == classified['track_id']:
                species_name, cls_conf = self._classify_crop(classified['crop'])
                combined_conf = box['conf'] * cls_conf

                crop = classified['crop']
                blur_variance = classified['blur_variance']
            
            detection_results.append(DetectionResult(
                track_id=box['track_id'],
                class_name=species_name,
                confidence=combined_conf, 
                bbox=box['bbox_norm'],
                blur_variance=blur_variance,
                crop=crop
            ))
             
        return detection_results

    def reset(self):
        self._classification_index = 0
        if hasattr(self.binary_model.predictor, 'trackers'):
            self.binary_model.predictor.trackers[0].reset()
