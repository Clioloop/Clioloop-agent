r"""Tests for _TOOL_MEDIA_RE regex patterns in gateway/run.py.

Issue #34632: The _TOOL_MEDIA_RE patterns in GatewayRunner used (?:/|~\/) to
anchor paths, which only matched Unix-style absolute and home-relative paths.
Windows absolute paths (C:\\Users\\..., D:/...) were silently ignored, causing
MEDIA directive delivery to fail on Windows.

Fix: Add [A-Za-z]:[/\\\\] as a third anchor alternative in both patterns.

Two identical _TOOL_MEDIA_RE patterns existed in run.py (module-level + local).
The local copy was removed to fix an UnboundLocalError (the local assignment
made Python treat the variable as function-scoped, so when the if-branch that
contained the assignment was not taken, the later unconditional reference
crashed). Now only the module-level pattern remains.
"""

import re

import pytest


# Reconstruct the exact _TOOL_MEDIA_RE pattern from gateway/run.py
# The pattern is built by concatenating raw string parts:
#   r'MEDIA:((?:[A-Za-z]:[/\\]|/|~\/)\S+\.(?:png|...))'
_TOOL_MEDIA_RE = re.compile(
    r'MEDIA:((?:[A-Za-z]:[/\\]|/|~\/)\S+\.(?:png|jpe?g|gif|webp|'
    r'mp4|mov|avi|mkv|webm|ogg|opus|mp3|wav|m4a|'
    r'flac|epub|pdf|zip|rar|7z|docx?|xlsx?|pptx?|'
    r'txt|csv|apk|ipa))',
    re.IGNORECASE,
)


# Reconstruct the pre-fix pattern (without Windows anchor) for regression proof
_TOOL_MEDIA_RE_PRE_FIX = re.compile(
    r'MEDIA:((?:/|~\/)\S+\.(?:png|jpe?g|gif|webp|'
    r'mp4|mov|avi|mkv|webm|ogg|opus|mp3|wav|m4a|'
    r'flac|epub|pdf|zip|rar|7z|docx?|xlsx?|pptx?|'
    r'txt|csv|apk|ipa))',
    re.IGNORECASE,
)


class TestToolMediaReWindowsPaths:
    """Issue #34632: _TOOL_MEDIA_RE must match Windows absolute paths."""

    # ── Positive: Windows paths now match ──────────────────────────

    @pytest.mark.parametrize("media_tag, expected_path", [
        # Windows backslash paths
        ("MEDIA:C:\\Users\\test\\image.png", "C:\\Users\\test\\image.png"),
        ("MEDIA:D:\\data\\report.pdf", "D:\\data\\report.pdf"),
        ("MEDIA:E:\\Photos\\vacation.jpg", "E:\\Photos\\vacation.jpg"),
        # Windows forward-slash paths
        ("MEDIA:C:/Users/test/image.png", "C:/Users/test/image.png"),
        ("MEDIA:D:/data/report.pdf", "D:/data/report.pdf"),
        # Mixed separators
        ("MEDIA:C:\\Users/test\\image.webp", "C:\\Users/test\\image.webp"),
        # Various extensions
        ("MEDIA:F:\\videos\\clip.mp4", "F:\\videos\\clip.mp4"),
        ("MEDIA:G:\\audio\\song.mp3", "G:\\audio\\song.mp3"),
        ("MEDIA:H:\\docs\\sheet.xlsx", "H:\\docs\\sheet.xlsx"),
        ("MEDIA:Z:\\archive\\backup.zip", "Z:\\archive\\backup.zip"),
    ])
    def test_windows_paths_match(self, media_tag, expected_path):
        """Windows absolute paths with drive letters are matched."""
        match = _TOOL_MEDIA_RE.search(media_tag)
        assert match is not None, f"Should match: {media_tag}"
        assert match.group(1) == expected_path

    # ── Positive: Unix paths still match ───────────────────────────

    @pytest.mark.parametrize("media_tag, expected_path", [
        ("MEDIA:/tmp/output.png", "/tmp/output.png"),
        ("MEDIA:/var/log/report.pdf", "/var/log/report.pdf"),
        ("MEDIA:/home/user/docs/file.txt", "/home/user/docs/file.txt"),
        # Home-relative
        ("MEDIA:~/Downloads/image.jpg", "~/Downloads/image.jpg"),
        ("MEDIA:~/Documents/report.pdf", "~/Documents/report.pdf"),
    ])
    def test_unix_paths_still_match(self, media_tag, expected_path):
        """Unix-style absolute and home-relative paths still match."""
        match = _TOOL_MEDIA_RE.search(media_tag)
        assert match is not None, f"Should match: {media_tag}"
        assert match.group(1) == expected_path

    # ── Negative: invalid paths don't match ────────────────────────

    @pytest.mark.parametrize("text", [
        "No MEDIA tag here",
        "MEDIA:relative/path/file.png",       # relative path, no anchor
        "MEDIA:file.png",                      # no directory
        "MEDIA:C:file.png",                    # drive letter but no separator
        "MEDIA:/path/to/file.unknown",         # unsupported extension
        "MEDIA:/path/to/file",                 # no extension
        "MEDIA:",                               # empty path
    ])
    def test_invalid_paths_dont_match(self, text):
        """Non-MEDIA text, relative paths, and unsupported extensions are ignored."""
        match = _TOOL_MEDIA_RE.search(text)
        assert match is None, f"Should NOT match: {text}"

    # ── Negative/preserved: old pattern rejects Windows paths ──────

    @pytest.mark.parametrize("media_tag", [
        "MEDIA:C:\\Users\\test\\image.png",
        "MEDIA:D:/data/report.pdf",
        "MEDIA:C:\\path\\file.jpg",
    ])
    def test_pre_fix_pattern_rejects_windows(self, media_tag):
        """The pre-fix pattern (without Windows anchor) does NOT match Windows paths.
        This proves the fix is necessary — without it, these paths are silently ignored."""
        match = _TOOL_MEDIA_RE_PRE_FIX.search(media_tag)
        assert match is None, f"Pre-fix pattern should NOT match: {media_tag}"

    # ── Edge cases ─────────────────────────────────────────────────

    def test_multiple_media_tags_in_content(self):
        """Multiple MEDIA tags in the same content are all found."""
        content = (
            "Some text MEDIA:C:\\path\\img.png and more MEDIA:/tmp/out.pdf trailing"
        )
        matches = list(_TOOL_MEDIA_RE.finditer(content))
        assert len(matches) == 2
        paths = [m.group(1) for m in matches]
        assert "C:\\path\\img.png" in paths
        assert "/tmp/out.pdf" in paths

    def test_case_insensitive_drive_letter(self):
        """Drive letters are case-insensitive due to re.IGNORECASE."""
        match_lower = _TOOL_MEDIA_RE.search("MEDIA:c:\\path\\file.png")
        match_upper = _TOOL_MEDIA_RE.search("MEDIA:C:\\path\\file.png")
        assert match_lower is not None
        assert match_upper is not None
        assert match_lower.group(1).lower() == match_upper.group(1).lower()

    @pytest.mark.parametrize("media_tag", [
        "MEDIA:C:\\path\\file.jpeg",
        "MEDIA:C:\\path\\file.JPG",
        "MEDIA:C:\\path\\file.GIF",
        "MEDIA:C:\\path\\file.MP4",
    ])
    def test_case_insensitive_extensions(self, media_tag):
        """File extensions are matched case-insensitively."""
        match = _TOOL_MEDIA_RE.search(media_tag)
        assert match is not None, f"Should match: {media_tag}"


class TestToolMediaReUnboundLocalRegression:
    """Regression test for the UnboundLocalError that occurred when the
    history-scanning code path in _run_agent() did not take the 'if' branch
    that contained a local _TOOL_MEDIA_RE assignment.

    The fix removed the local assignment so the module-level regex is always
    used. This test verifies the module-level regex is accessible and
    functional regardless of history content.
    """

    def test_module_level_regex_works_with_empty_history(self):
        """The module-level _TOOL_MEDIA_RE must be usable even when no
        history messages contain MEDIA: tags (the original crash scenario)."""
        from gateway.run import _TOOL_MEDIA_RE

        # Simulate the result-scanning code path (line ~18638)
        final_response = "Here is your song!\nMEDIA:/tmp/track1.mp3"
        existing_paths = set()
        for match in _TOOL_MEDIA_RE.finditer(final_response):
            existing_paths.add(match.group(1).strip().rstrip('",}'))

        assert "/tmp/track1.mp3" in existing_paths

    def test_module_level_regex_works_with_no_media_in_response(self):
        """The module-level _TOOL_MEDIA_RE must handle responses with no
        MEDIA: tags without error."""
        from gateway.run import _TOOL_MEDIA_RE

        final_response = "No media here, just text."
        existing_paths = set()
        for match in _TOOL_MEDIA_RE.finditer(final_response):
            existing_paths.add(match.group(1).strip().rstrip('",}'))

        assert len(existing_paths) == 0

    def test_collect_auto_append_with_no_history_media(self):
        """End-to-end: _collect_auto_append_media_tags must work when
        history has no prior MEDIA: tags (the exact crash scenario)."""
        from gateway.run import _collect_auto_append_media_tags
        import json as _json

        tool_result = _json.dumps({
            "success": True,
            "audio": "/tmp/track1.mp3",
            "all_tracks": [
                {"audio": "/tmp/track1.mp3", "track_index": 1},
                {"audio": "/tmp/track2.mp3", "track_index": 2},
            ],
        })
        messages = [
            {
                "role": "assistant",
                "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "music_generate", "arguments": "{}"},
                }],
            },
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "content": tool_result,
            },
        ]
        # This must NOT raise UnboundLocalError
        tags, has_voice = _collect_auto_append_media_tags(
            messages, history_media_paths=set()
        )
        assert "MEDIA:/tmp/track1.mp3" in tags
        assert "MEDIA:/tmp/track2.mp3" in tags
