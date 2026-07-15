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


def test_unpack_zip_lists_nested_archive_without_extracting(tmp_path, capsys):
    inner = make_zip(tmp_path / "inner.zip", [("deep.log", b"x")])
    archive = make_zip(tmp_path / "outer.zip", [("inner.zip", inner.read_bytes()), ("top.log", b"y")])
    dest = tmp_path / "out"
    manifest = jira_utils.unpack_archive(archive, dest, budget_bytes=10_000)
    assert [e["path"] for e in manifest] == ["top.log"]
    assert not (dest / "inner.zip").exists()
    assert "nested archive: inner.zip (not extracted)" in capsys.readouterr().out


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
