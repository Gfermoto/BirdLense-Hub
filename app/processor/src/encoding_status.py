"""Shared status for recording encoding (CPU vs VA-API). Used by heartbeat."""

_last_encoding_used = None  # "cpu" | "vaapi" | "x264_cpu" | "v4l2m2m" | "omx"


def set_last_encoding_used(used: str):
    global _last_encoding_used
    _last_encoding_used = used


def get_last_encoding_used():
    return _last_encoding_used
