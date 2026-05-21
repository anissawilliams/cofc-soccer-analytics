"""
compress.py — Compress XML files and upload to Supabase blob storage
"""

import gzip
import shutil
from pathlib import Path

from config import supabase, BLOB_BUCKET


def compress_file(src_path: Path) -> Path:
    """
    Gzip compress an XML file.
    Returns path to compressed .gz file (in same directory).
    """
    gz_path = src_path.with_suffix(src_path.suffix + ".gz")
    with open(src_path, "rb") as f_in:
        with gzip.open(gz_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)

    original_kb   = src_path.stat().st_size / 1024
    compressed_kb = gz_path.stat().st_size / 1024
    reduction     = 100 - (compressed_kb / original_kb * 100)
    print(f"  Compressed {src_path.name}: "
          f"{original_kb:.1f}KB → {compressed_kb:.1f}KB "
          f"({reduction:.0f}% reduction)")
    return gz_path


def upload_blob(local_path: Path, blob_path: str) -> str:
    """
    Upload a file to Supabase Storage.
    Returns the blob_path stored (for saving in matches table).
    Uses upsert so re-ingestion doesn't fail.
    """
    with open(local_path, "rb") as f:
        supabase.storage.from_(BLOB_BUCKET).upload(
            path=blob_path,
            file=f,
            file_options={
                "content-type": "application/gzip",
                "upsert": "true"
            }
        )
    print(f"  Uploaded → {BLOB_BUCKET}/{blob_path}")
    return blob_path


def compress_and_upload(src_path: Path, blob_path: str) -> str:
    """
    Compress a file and upload to blob storage.
    Cleans up the .gz file after upload.
    Returns blob_path.
    """
    gz_path = compress_file(src_path)
    try:
        upload_blob(gz_path, blob_path)
    finally:
        gz_path.unlink()   # always clean up temp file
    return blob_path


def build_blob_path(season: str, folder_slug: str, filename: str) -> str:
    """
    Build the blob storage path for a file.
    e.g. matches/2025/2025-11-02_uncw/2025-11-02_uncw_cfc_sportscode.xml.gz
    """
    return f"matches/{season}/{folder_slug}/{filename}.gz"
