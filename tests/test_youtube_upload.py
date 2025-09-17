import importlib
import json

import youtube_upload


def test_configured_scopes_defaults_when_env_missing(monkeypatch):
    monkeypatch.delenv("YT_SCOPES", raising=False)
    module = importlib.reload(youtube_upload)
    assert module._configured_scopes() == module.SCOPES


def test_configured_scopes_parses_commas_and_whitespace(monkeypatch):
    monkeypatch.setenv(
        "YT_SCOPES",
        "scope.one scope.two,scope.three\n https://example.com/custom",
    )
    # Reload to ensure module level caches don't interfere with env lookups.
    module = importlib.reload(youtube_upload)
    assert module._configured_scopes() == [
        "scope.one",
        "scope.two",
        "scope.three",
        "https://example.com/custom",
    ]


def test_try_upload_youtube_times_out_when_no_progress(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"stub video data")

    monkeypatch.setenv("YT_UPLOAD_MAX_IDLE_SECONDS", "5")
    monkeypatch.setenv("YT_UPLOAD_MAX_TOTAL_SECONDS", "15")

    fake_creds = object()
    monkeypatch.setattr(youtube_upload, "_creds", lambda: fake_creds)

    class FakeMediaFileUpload:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    monkeypatch.setattr(youtube_upload, "MediaFileUpload", FakeMediaFileUpload)

    class FakeTime:
        def __init__(self):
            self._now = 0.0

        def monotonic(self):
            return self._now

        def sleep(self, seconds):
            self._now += float(seconds)

        def advance(self, seconds):
            self._now += float(seconds)

    fake_time = FakeTime()
    monkeypatch.setattr(youtube_upload.time, "monotonic", fake_time.monotonic)
    monkeypatch.setattr(youtube_upload.time, "sleep", fake_time.sleep)

    class FakeRequest:
        def __init__(self):
            self.calls = 0

        def next_chunk(self):
            self.calls += 1
            fake_time.advance(3)
            return None, None

    fake_request = FakeRequest()

    class FakeVideos:
        def insert(self, **kwargs):
            return fake_request

    class FakeYoutube:
        def videos(self):
            return FakeVideos()

    monkeypatch.setattr(youtube_upload, "build", lambda *args, **kwargs: FakeYoutube())
    monkeypatch.setattr(youtube_upload, "_check_video_status", lambda youtube, vid: {})

    result = youtube_upload.try_upload_youtube(
        video_path.as_posix(),
        title="Test",
        description="Desc",
    )

    assert result is None

    error_path = tmp_path / "out" / "youtube_error.json"
    assert error_path.exists()
    error_data = json.loads(error_path.read_text(encoding="utf-8"))
    assert "stalled" in error_data.get("error", "").lower()


def test_try_upload_youtube_returns_url_on_success(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"video")

    fake_creds = object()
    monkeypatch.setattr(youtube_upload, "_creds", lambda: fake_creds)

    class FakeMediaFileUpload:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    monkeypatch.setattr(youtube_upload, "MediaFileUpload", FakeMediaFileUpload)

    class FakeStatus:
        def __init__(self, fraction, bytes_progress):
            self._fraction = fraction
            self.resumable_progress = bytes_progress

        def progress(self):
            return self._fraction

    chunks = [
        (FakeStatus(0.1, 1_000), None),
        (FakeStatus(0.6, 6_000), None),
        (None, {"id": "abc123"}),
    ]

    class FakeRequest:
        def next_chunk(self):
            return chunks.pop(0)

    fake_request = FakeRequest()

    class FakeVideos:
        def insert(self, **kwargs):
            return fake_request

    class FakeYoutube:
        def videos(self):
            return FakeVideos()

    monkeypatch.setattr(youtube_upload, "build", lambda *args, **kwargs: FakeYoutube())

    def fake_status_check(youtube, vid):
        return {
            "items": [
                {"status": {"uploadStatus": "processed", "privacyStatus": "public"}}
            ]
        }

    monkeypatch.setattr(youtube_upload, "_check_video_status", fake_status_check)

    url = youtube_upload.try_upload_youtube(
        video_path.as_posix(),
        title="Hello",
        description="World",
    )

    assert url == "https://youtu.be/abc123"

