#!/usr/bin/env python3
"""Fix the video section in jetson-nano-edge-setup-and-migration.md (binary-safe)."""
import re

path = "docs/strategy/jetson-nano-edge-setup-and-migration.md"
with open(path, "rb") as f:
    data = f.read()

# Find the video section header and replace the whole table
old_header = b"**\xd0\x92\xd0\xb8\xd0\xb4\xd0\xb5\xd0\xbe (Jetson, \xd0\xb1\xd0\xb5\xd0\xb7 Intel):**"
new_header = b"**\xd0\x92\xd0\xb8\xd0\xb4\xd0\xb5\xd0\xbe (Jetson, HW acceleration):**"

new_table = b"""\
| \xd0\xa4\xd1\x83\xd0\xbd\xd0\xba\xd1\x86\xd0\xb8\xd1\x8f | \xd0\x97\xd0\xbd\xd0\xb0\xd1\x87\xd0\xb5\xd0\xbd\xd0\xb8\xd0\xb5 | \xd0\x96\xd0\xb5\xd0\xbb\xd0\xb5\xd0\xb7\xd0\xbe |
|---------|----------|--------|
| \xd0\x97\xd0\xb0\xd1\x85\xd0\xb2\xd0\xb0\xd1\x82 lores (motion/YOLO) | `capture_backend: ffmpeg_nvmpi`, GStreamer NVDEC | **HW NVDEC** \xd1\x87\xd0\xb5\xd1\x80\xd0\xb5\xd0\xb7 `nvv4l2decoder` |
| \xd0\x97\xd0\xb0\xd0\xbf\xd0\xb8\xd1\x81\xd1\x8c main | `encoding: jetson`, `h264_v4l2m2m` \xe2\x86\x92 fallback `h264_omx` \xe2\x86\x92 `libx264` | **HW V4L2 mem2mem / OpenMAX IL** |
| VA-API / Intel iGPU | **\xd0\xb2\xd1\x8b\xd0\xba\xd0\xbb\xd1\x8e\xd1\x87\xd0\xb5\xd0\xbd\xd0\xbe** | `record_with_vaapi: false` |"""

# Match everything from header to the blank line after the table
pattern = re.compile(
    re.escape(old_header) + b"\n\n" +
    b"(\| [^\n]*\n\|[-| ]+\n(?:[|][^\n]*\n)+)"
)

m = pattern.search(data)
if m:
    start = m.start()
    end = m.end()
    replacement = new_header + b"\n\n" + new_table
    data = data[:start] + replacement + data[end:]
    with open(path, "wb") as f:
        f.write(data)
    print("OK: replaced video section")
else:
    print("FAIL: pattern not found")
    print("Header found?", old_header in data)
    # find what's around the header
    idx = data.find(b"\xd0\x92\xd0\xb8\xd0\xb4\xd0\xb5\xd0\xbe (Jetson")
    if idx >= 0:
        chunk = data[idx:idx+600]
        for i, line in enumerate(chunk.split(b"\n")[:8]):
            print(repr(line))