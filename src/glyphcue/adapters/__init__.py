"""Narrow contracts isolating third-party dependencies from domain code.

Each module here defines a Protocol that a future concrete adapter
(pysubs2, an OCR runtime, PyAV, FFmpeg) will implement. Domain code depends
only on these contracts, never on the vendor libraries directly.
"""
