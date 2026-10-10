#!/usr/bin/env python3
"""Render the app's geometric three-bar mark without image dependencies."""
from pathlib import Path
import struct
import zlib

def chunk(kind, data):
    return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data))

for size in (180, 192, 512):
    pixels = bytearray()
    for y in range(size):
        pixels.append(0)
        for x in range(size):
            color = (25, 53, 48)
            for left, top, right, bottom, ink in ((.26,.28,.37,.72,(245,244,238)),(.445,.42,.555,.72,(128,205,182)),(.63,.55,.74,.72,(245,165,131))):
                if left*size <= x < right*size and top*size <= y < bottom*size:
                    color = ink
            pixels.extend(color)
    data = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!IIBBBBB', size, size, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(pixels,9)) + chunk(b'IEND',b'')
    (Path(__file__).parent / 'web' / f'icon-{size}.png').write_bytes(data)
