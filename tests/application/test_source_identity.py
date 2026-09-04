from glyphcue.application.source_identity import normalize_source_id


def test_windows_normalizes_differently_cased_paths_to_the_same_source_id(monkeypatch, tmp_path):
    # Windows filesystems are case-insensitive: two paths differing only in
    # case must resolve to the SAME source identity there, or a repeated
    # open of the identical file under different casing would silently
    # split its persisted cues/track-groups across two "different" sources.
    # CI runs on ubuntu-latest, where sys.platform is never "win32", so
    # this branch is otherwise never exercised by the automated suite.
    monkeypatch.setattr("glyphcue.application.source_identity.sys.platform", "win32")
    lower = tmp_path / "video.mp4"
    upper = tmp_path / "VIDEO.MP4"

    assert normalize_source_id(lower) == normalize_source_id(upper)


def test_windows_uses_forward_slashes_not_backslashes(monkeypatch, tmp_path):
    monkeypatch.setattr("glyphcue.application.source_identity.sys.platform", "win32")

    source_id = normalize_source_id(tmp_path / "clip.mp4")

    assert "\\" not in source_id


def test_posix_preserves_case_so_differently_cased_paths_stay_distinct(monkeypatch, tmp_path):
    # The inverse contract: on a case-sensitive filesystem, "video.mp4" and
    # "VIDEO.MP4" are two real, different files and must never collapse
    # into one source identity.
    monkeypatch.setattr("glyphcue.application.source_identity.sys.platform", "linux")
    lower = tmp_path / "video.mp4"
    upper = tmp_path / "VIDEO.MP4"

    assert normalize_source_id(lower) != normalize_source_id(upper)
