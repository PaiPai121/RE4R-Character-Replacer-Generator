"""Uncompressed sRGB DDS fallback for hosts without the Windows image codec."""
import struct
from pathlib import Path
import bpy
import numpy as np


def write_rgba8_dds(source, destination):
    image = bpy.data.images.load(str(source), check_existing=False)
    try:
        width, height = image.size
        pixels = np.empty(width*height*4, dtype=np.float32)
        image.pixels.foreach_get(pixels)
        # Blender pixels are bottom-up; DDS scanlines are top-down.
        rgba = np.rint(np.clip(pixels, 0, 1)*255).astype(np.uint8).reshape(height, width, 4)[::-1].tobytes()
        pixel_format = struct.pack('<II4sIIIII', 32, 4, b'DX10', 0, 0, 0, 0, 0)
        # RE's DDS converter expects a depth of one for 2D surfaces.
        header = struct.pack('<7I11I32s5I', 124, 0x100f, height, width, width*4, 1, 1,
                             *([0]*11), pixel_format, 0x1000, 0, 0, 0, 0)
        Path(destination).write_bytes(b'DDS '+header+struct.pack('<5I',29,3,0,1,0)+rgba)
    finally:
        bpy.data.images.remove(image)
