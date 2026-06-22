import numpy as np

class StreamMapper:
    @classmethod
    def detector(cls, frames):
        # Consolidated geometry logic from frame_geometry.py
        # Frame processing logic for detection
        return processed_frames

    @classmethod
    def overlay(cls, frames, detections):
        # Apply detections to frames with bounding boxes
        return annotated_frames

    @classmethod
    def crop(cls, frames, regions):
        """Extract specific regions from frames
        Args:
            regions: List of (x1, y1, x2, y2) tuples
        """
        return cropped_frames

    @classmethod
    def remap(cls, frames, new_size):
        """Resize frames to new dimensions
        Args:
            new_size: (width, height)
        """
        return resized_frames