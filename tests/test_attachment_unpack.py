import io
import tarfile
import zipfile
from pathlib import Path

import jira_utils


def make_zip(path: Path, entries) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in entries:
            zf.writestr(name, data)
    return path


def test_is_archive_and_stem():
    assert jira_utils._is_archive("logs.zip")
    assert jira_utils._is_archive("bundle.tar.gz")
    assert jira_utils._is_archive("bundle.TGZ")
    assert not jira_utils._is_archive("report.pdf")
    assert not jira_utils._is_archive("video.7z")  # unsupported on purpose
    assert jira_utils._archive_stem("logs.zip") == "logs"
    assert jira_utils._archive_stem("bundle.tar.gz") == "bundle"


def test_safe_relpath_rejects_escapes():
    assert jira_utils._safe_relpath("a/b.txt") == "a/b.txt"
    assert jira_utils._safe_relpath("./a/./b.txt") == "a/b.txt"
    assert jira_utils._safe_relpath("../evil.txt") is None
    assert jira_utils._safe_relpath("a/../../evil.txt") is None
    assert jira_utils._safe_relpath("/abs/evil.txt") is None
    assert jira_utils._safe_relpath("C:\\evil.txt") is None
    assert jira_utils._safe_relpath("") is None


def test_unpack_zip_extracts_files(tmp_path):
    archive = make_zip(tmp_path / "logs.zip", [("a.log", b"alpha"), ("sub/b.log", b"beta")])
    dest = tmp_path / "out"
    manifest = jira_utils.unpack_archive(archive, dest, budget_bytes=1024)
    assert (dest / "a.log").read_bytes() == b"alpha"
    assert (dest / "sub" / "b.log").read_bytes() == b"beta"
    assert sorted(e["path"] for e in manifest) == ["a.log", "sub/b.log"]
    assert all(e["size"] > 0 for e in manifest)


def test_unpack_zip_skips_traversal_and_absolute(tmp_path, capsys):
    archive = make_zip(
        tmp_path / "evil.zip",
        [("../escape.txt", b"x"), ("/abs.txt", b"x"), ("ok.txt", b"fine")],
    )
    dest = tmp_path / "out"
    manifest = jira_utils.unpack_archive(archive, dest, budget_bytes=1024)
    assert [e["path"] for e in manifest] == ["ok.txt"]
    assert not (tmp_path / "escape.txt").exists()
    out = capsys.readouterr().out
    assert out.count("unsafe path") == 2


def test_unpack_zip_skips_symlink_entry(tmp_path, capsys):
    import stat
    path = tmp_path / "links.zip"
    with zipfile.ZipFile(path, "w") as zf:
        link = zipfile.ZipInfo("link.txt")
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        zf.writestr(link, "/etc/passwd")
        zf.writestr("ok.txt", b"fine")
    dest = tmp_path / "out"
    manifest = jira_utils.unpack_archive(path, dest, budget_bytes=1024)
    assert [e["path"] for e in manifest] == ["ok.txt"]
    assert not (dest / "link.txt").exists()
    assert "link skipped: link.txt" in capsys.readouterr().out


def test_unpack_zip_extracts_nested_archive_one_level(tmp_path, capsys):
    inner = make_zip(tmp_path / "inner.zip", [("deep.log", b"x" * 4)])
    archive = make_zip(
        tmp_path / "outer.zip",
        [("reports/inner.zip", inner.read_bytes()), ("top.log", b"y")],
    )
    dest = tmp_path / "out"
    manifest = jira_utils.unpack_archive(archive, dest, budget_bytes=10_000)
    assert (dest / "reports" / "inner" / "deep.log").read_bytes() == b"x" * 4
    assert not (dest / "reports" / "inner.zip").exists()  # blob never written
    assert sorted(e["path"] for e in manifest) == ["reports/inner/deep.log", "top.log"]
    assert "nested archive: reports/inner.zip (extracting)" in capsys.readouterr().out


def test_unpack_stops_at_budget(tmp_path, capsys):
    archive = make_zip(tmp_path / "big.zip", [("one.log", b"x" * 8), ("two.log", b"y" * 8)])
    dest = tmp_path / "out"
    manifest = jira_utils.unpack_archive(archive, dest, budget_bytes=10)
    assert [e["path"] for e in manifest] == ["one.log"]
    assert not (dest / "two.log").exists()
    assert "BUDGET EXCEEDED" in capsys.readouterr().out


def make_tar(path: Path, entries, mode: str = "w:gz") -> Path:
    with tarfile.open(path, mode) as tf:
        for name, data in entries:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = 1750000000
            tf.addfile(info, io.BytesIO(data))
    return path


def test_unpack_tarball(tmp_path):
    archive = make_tar(tmp_path / "bundle.tar.gz", [("logs/app.log", b"hello")])
    dest = tmp_path / "out"
    manifest = jira_utils.unpack_archive(archive, dest, budget_bytes=1024)
    assert (dest / "logs" / "app.log").read_bytes() == b"hello"
    assert manifest[0]["path"] == "logs/app.log"
    assert manifest[0]["mtime"]  # non-empty ISO string


def test_unpack_tar_skips_symlink_and_traversal(tmp_path, capsys):
    path = tmp_path / "evil.tar"
    with tarfile.open(path, "w") as tf:
        link = tarfile.TarInfo("link.txt")
        link.type = tarfile.SYMTYPE
        link.linkname = "/etc/passwd"
        tf.addfile(link)
        bad = tarfile.TarInfo("../escape.txt")
        bad.size = 1
        tf.addfile(bad, io.BytesIO(b"x"))
        ok = tarfile.TarInfo("ok.txt")
        ok.size = 2
        tf.addfile(ok, io.BytesIO(b"ok"))
    dest = tmp_path / "out"
    manifest = jira_utils.unpack_archive(path, dest, budget_bytes=1024)
    assert [e["path"] for e in manifest] == ["ok.txt"]
    assert not (tmp_path / "escape.txt").exists()
    out = capsys.readouterr().out
    assert "link skipped: link.txt" in out
    assert "unsafe path" in out


class _FakeResp:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        pass


def _issue(atts):
    return {"key": "CDS2ASV-1", "fields": {"attachment": atts}}


def test_download_skips_oversize(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(jira_utils, "get_auth", lambda: None)

    def no_get(*a, **k):
        raise AssertionError("must not download an over-cap file")

    monkeypatch.setattr(jira_utils.requests, "get", no_get)
    att = {"filename": "huge.log", "id": "1", "size": 60 * 1024 * 1024, "mimeType": "text/plain"}
    written = jira_utils.download_attachments(_issue([att]), tmp_path)
    assert written == []
    assert "skip (size)" in capsys.readouterr().out


def test_download_unpacks_zip(monkeypatch, tmp_path):
    monkeypatch.setattr(jira_utils, "get_auth", lambda: None)
    zip_bytes = (make_zip(tmp_path / "src.zip", [("app.log", b"boom")])).read_bytes()
    monkeypatch.setattr(jira_utils.requests, "get", lambda *a, **k: _FakeResp(zip_bytes))
    att = {"filename": "logs.zip", "id": "2", "size": len(zip_bytes), "mimeType": "application/zip"}
    jira_utils.download_attachments(_issue([att]), tmp_path, unpack=True)
    assert (tmp_path / "CDS2ASV-1" / "logs.zip").exists()
    assert (tmp_path / "CDS2ASV-1" / "_unpacked" / "logs" / "app.log").read_bytes() == b"boom"


def test_download_without_unpack_leaves_archive_packed(monkeypatch, tmp_path):
    monkeypatch.setattr(jira_utils, "get_auth", lambda: None)
    zip_bytes = (make_zip(tmp_path / "src.zip", [("app.log", b"boom")])).read_bytes()
    monkeypatch.setattr(jira_utils.requests, "get", lambda *a, **k: _FakeResp(zip_bytes))
    att = {"filename": "logs.zip", "id": "3", "size": len(zip_bytes), "mimeType": "application/zip"}
    jira_utils.download_attachments(_issue([att]), tmp_path)
    assert not (tmp_path / "CDS2ASV-1" / "_unpacked").exists()


def test_download_survives_corrupt_archive(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(jira_utils, "get_auth", lambda: None)
    corrupt = b"PK\x03\x04 this is not a real zip"
    good_png = b"fake image bytes"
    responses = {"9": corrupt, "10": good_png}

    def fake_get(url, **kwargs):
        return _FakeResp(responses[url.rsplit("/", 1)[-1]])

    monkeypatch.setattr(jira_utils.requests, "get", fake_get)
    atts = [
        {"filename": "broken.zip", "id": "9", "size": len(corrupt), "mimeType": "application/zip"},
        {"filename": "shot.png", "id": "10", "size": len(good_png), "mimeType": "image/png"},
    ]
    written = jira_utils.download_attachments(_issue(atts), tmp_path, unpack=True)
    assert [p.name for p in written] == ["broken.zip", "shot.png"]
    assert "UNPACK FAILED: broken.zip" in capsys.readouterr().out


def test_download_survives_member_collision(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(jira_utils, "get_auth", lambda: None)
    zip_bytes = (make_zip(tmp_path / "src.zip", [("a", b"file"), ("a/b.txt", b"child")])).read_bytes()
    monkeypatch.setattr(jira_utils.requests, "get", lambda *a, **k: _FakeResp(zip_bytes))
    att = {"filename": "clash.zip", "id": "11", "size": len(zip_bytes), "mimeType": "application/zip"}
    written = jira_utils.download_attachments(_issue([att]), tmp_path, unpack=True)
    assert [p.name for p in written] == ["clash.zip"]
    assert "UNPACK FAILED: clash.zip" in capsys.readouterr().out


# ── nested extraction, one level (0.24.0) ───────────────────────────────

def test_unpack_nested_tarball_inside_zip(tmp_path):
    inner = make_tar(tmp_path / "inner.tar.gz", [("logs/app.log", b"hello")])
    archive = make_zip(tmp_path / "outer.zip", [("inner.tar.gz", inner.read_bytes())])
    dest = tmp_path / "out"
    manifest = jira_utils.unpack_archive(archive, dest, budget_bytes=10_000)
    assert (dest / "inner" / "logs" / "app.log").read_bytes() == b"hello"
    assert manifest[0]["path"] == "inner/logs/app.log"


def test_unpack_depth_two_archive_stays_packed(tmp_path, capsys):
    deepest = make_zip(tmp_path / "deepest.zip", [("core.log", b"z")])
    inner = make_zip(
        tmp_path / "inner.zip",
        [("deepest.zip", deepest.read_bytes()), ("mid.log", b"m")],
    )
    archive = make_zip(tmp_path / "outer.zip", [("inner.zip", inner.read_bytes())])
    dest = tmp_path / "out"
    manifest = jira_utils.unpack_archive(archive, dest, budget_bytes=10_000)
    assert [e["path"] for e in manifest] == ["inner/mid.log"]
    assert not (dest / "inner" / "deepest").exists()
    assert ("nested archive (depth 2): inner/deepest.zip (not extracted)"
            in capsys.readouterr().out)


def test_unpack_budget_shared_across_nesting(tmp_path, capsys):
    # make_zip stores uncompressed (ZIP_STORED), so sizes are predictable.
    # Budget 9000: outer first.log (4000) + nested one.log (2000) +
    # two.log (2000) = 8000 fit; three.log (2000) would hit 10000 → stop.
    inner = make_zip(
        tmp_path / "inner.zip",
        [("one.log", b"a" * 2000), ("two.log", b"b" * 2000), ("three.log", b"c" * 2000)],
    )
    archive = make_zip(
        tmp_path / "outer.zip",
        [("first.log", b"x" * 4000), ("inner.zip", inner.read_bytes())],
    )
    dest = tmp_path / "out"
    manifest = jira_utils.unpack_archive(archive, dest, budget_bytes=9000)
    assert [e["path"] for e in manifest] == ["first.log", "inner/one.log", "inner/two.log"]
    assert not (dest / "inner" / "three.log").exists()
    assert "BUDGET EXCEEDED" in capsys.readouterr().out


def test_unpack_nested_archive_too_large_stays_packed(tmp_path, capsys):
    inner = make_zip(tmp_path / "inner.zip", [("big.log", b"x" * 600)])
    archive = make_zip(
        tmp_path / "outer.zip",
        [("inner.zip", inner.read_bytes()), ("top.log", b"y" * 8)],
    )
    dest = tmp_path / "out"
    manifest = jira_utils.unpack_archive(archive, dest, budget_bytes=300)
    assert [e["path"] for e in manifest] == ["top.log"]
    assert "nested archive: inner.zip (too large, not extracted)" in capsys.readouterr().out


def test_unpack_survives_malformed_nested_archive(tmp_path, capsys):
    archive = make_zip(
        tmp_path / "outer.zip",
        [("broken.zip", b"PK\x03\x04 not really a zip"), ("ok.log", b"fine")],
    )
    dest = tmp_path / "out"
    manifest = jira_utils.unpack_archive(archive, dest, budget_bytes=10_000)
    assert [e["path"] for e in manifest] == ["ok.log"]
    assert "NESTED UNPACK FAILED: broken.zip" in capsys.readouterr().out


def test_unpack_nested_guards_apply(tmp_path, capsys):
    import stat
    inner_path = tmp_path / "inner.zip"
    with zipfile.ZipFile(inner_path, "w") as zf:
        zf.writestr("../escape.txt", b"x")
        link = zipfile.ZipInfo("link.txt")
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        zf.writestr(link, "/etc/passwd")
        zf.writestr("ok.log", b"fine")
    archive = make_zip(tmp_path / "outer.zip", [("inner.zip", inner_path.read_bytes())])
    dest = tmp_path / "out"
    manifest = jira_utils.unpack_archive(archive, dest, budget_bytes=10_000)
    assert [e["path"] for e in manifest] == ["inner/ok.log"]
    assert not (tmp_path / "escape.txt").exists()
    out = capsys.readouterr().out
    assert "unsafe path" in out
    assert "link skipped" in out
