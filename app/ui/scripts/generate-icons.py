#!/usr/bin/env python3
"""Generate icon sizes from logo.png for PWA and favicons."""
import sys
from pathlib import Path

from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = SCRIPT_DIR.parent / "public"
LOGO = PUBLIC_DIR / "logo.png"

SIZES = [
    (96, "favicon-96x96.png"),
    (180, "apple-touch-icon.png"),
    (192, "web-app-manifest-192x192.png"),
    (512, "web-app-manifest-512x512.png"),
]


def main():
    if not LOGO.exists():
        print(f"Logo not found: {LOGO}", file=sys.stderr)
        return 1
    try:
        img = Image.open(LOGO).convert("RGBA")
    except Exception as e:
        print(f"Failed to open logo: {e}", file=sys.stderr)
        return 1
    for size, name in SIZES:
        out = PUBLIC_DIR / name
        try:
            resized = img.resize((size, size), Image.Resampling.LANCZOS)
            resized.save(out, "PNG", optimize=True)
            print(f"Created {out} ({size}x{size})")
        except Exception as e:
            print(f"Failed to save {out}: {e}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
