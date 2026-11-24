"""Snapshot validation (SYNTHETIC fixtures) + no-false-positive check on real raw files."""
import gzip
import zipfile

import pytest

from unlock.sources import gunzip_in_place, validate_snapshot


def test_validate_accepts_good_files(tmp_path):
    (tmp_path / "a.json").write_text('[{"k": 1}]', encoding="utf-8")
    (tmp_path / "b.csv").write_text("a;b\n1;2\n", encoding="utf-8")
    (tmp_path / "c.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (tmp_path / "d.xml").write_text("<r><a/></r>", encoding="utf-8")
    with zipfile.ZipFile(tmp_path / "e.zip", "w") as z:
        z.writestr("x.txt", "hello")
    for f in ("a.json", "b.csv", "c.csv", "d.xml", "e.zip"):
        validate_snapshot(tmp_path / f)


def test_validate_rejects_corrupt_files(tmp_path):
    (tmp_path / "a.json").write_bytes(b"\x1f\x8bgarbage-not-json")
    (tmp_path / "b.json").write_text('[{"k": ', encoding="utf-8")
    (tmp_path / "c.csv").write_text("only-header-no-rows\n", encoding="utf-8")
    (tmp_path / "d.csv").write_text("singlecolumn\nvalue\n", encoding="utf-8")
    (tmp_path / "e.xml").write_text("<r><unclosed>", encoding="utf-8")
    (tmp_path / "f.zip").write_bytes(b"PK\x03\x04truncated")
    for f in ("a.json", "b.json", "c.csv", "d.csv", "e.xml", "f.zip"):
        with pytest.raises(ValueError):
            validate_snapshot(tmp_path / f)


def test_gunzip_in_place_transparent(tmp_path):
    p = tmp_path / "a.json"
    p.write_bytes(gzip.compress(b'[{"k": 1}]'))
    assert gunzip_in_place(p) is True
    validate_snapshot(p)
    q = tmp_path / "b.json"
    q.write_text("[]", encoding="utf-8")
    assert gunzip_in_place(q) is False


def test_validate_with_explicit_suffix_for_part_files(tmp_path):
    p = tmp_path / "a.json.part"
    p.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError):
        validate_snapshot(p, suffix=".json")
