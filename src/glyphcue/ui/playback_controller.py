from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer


class PlaybackController(QObject):
    """Human playback only (DESIGN.md / ROADMAP.md Milestone 2 scope).

    Wraps Qt Multimedia for Play/Pause, seek, and cue-span replay. This
    is entirely separate from PyAvMediaFrameSource, which handles
    algorithmic analysis decoding -- Qt playback and PyAV analysis never
    share a decoding pipeline.
    """

    def __init__(self) -> None:
        super().__init__()
        self._player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self._player.setAudioOutput(self._audio_output)
        self._span_end_ms: int | None = None
        self._loop_start_ms: int | None = None
        self._loop_end_ms: int | None = None
        self._loop_enabled: bool = False
        self._last_position_ms: int = 0
        self._player.mediaStatusChanged.connect(self._on_media_status_changed)
        self._player.positionChanged.connect(self._on_playback_position_changed)

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if status in (QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia):
            if self._player.playbackState() == QMediaPlayer.PlaybackState.StoppedState:
                self._player.pause()

    @property
    def player(self) -> QMediaPlayer:
        return self._player

    @property
    def duration_seconds(self) -> float:
        return self._player.duration() / 1000.0

    @property
    def position_seconds(self) -> float:
        pos = self._player.position()
        if pos == 0 and self._last_position_ms > 0:
            return self._last_position_ms / 1000.0
        return pos / 1000.0

    def load(self, path: Path) -> None:
        self._last_position_ms = 0
        self._player.setSource(QUrl.fromLocalFile(str(path)))
        self.pause()

    def play(self) -> None:
        self._player.play()

    def pause(self) -> None:
        self._player.pause()

    def toggle_play_pause(self) -> None:
        """Space's real behavior (DESIGN.md section 10.2: `Space = Play
        / Pause`) -- one stable toggle, not two separate bindings a
        caller has to track playback state to choose between."""
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.pause()
        else:
            self.play()

    def seek(self, seconds: float) -> None:
        ms = round(seconds * 1000)
        self._last_position_ms = ms
        self._player.setPosition(ms)

    def set_video_output(self, video_output) -> None:
        self._player.setVideoOutput(video_output)

    def play_span(self, start_seconds: float, end_seconds: float) -> None:
        """Cue-span replay: seek to `start_seconds`, play, and
        automatically pause once playback reaches `end_seconds`."""
        self._span_end_ms = round(end_seconds * 1000)
        self._player.positionChanged.connect(self._on_position_changed_during_span)
        self.play()
        self.seek(start_seconds)

    @property
    def is_loop_enabled(self) -> bool:
        return self._loop_enabled

    @property
    def loop_range(self) -> tuple[float, float] | None:
        if self._loop_start_ms is not None and self._loop_end_ms is not None:
            return (self._loop_start_ms / 1000.0, self._loop_end_ms / 1000.0)
        return None

    def set_ab_loop(self, start_seconds: float, end_seconds: float, enabled: bool = True) -> bool:
        """Configures the preview/calibration A-B loop range.

        Validates that `start_seconds >= 0` and `end_seconds > start_seconds`.
        Returns True if the range is valid and set, or False if invalid.
        """
        if start_seconds < 0.0 or end_seconds <= start_seconds:
            self._loop_enabled = False
            return False
        self._loop_start_ms = round(start_seconds * 1000)
        self._loop_end_ms = round(end_seconds * 1000)
        self._loop_enabled = enabled
        return True

    def set_loop_enabled(self, enabled: bool) -> None:
        if enabled:
            if (
                self._loop_start_ms is not None
                and self._loop_end_ms is not None
                and self._loop_end_ms > self._loop_start_ms
            ):
                self._loop_enabled = True
            else:
                self._loop_enabled = False
        else:
            self._loop_enabled = False

    def clear_ab_loop(self) -> None:
        self._loop_enabled = False
        self._loop_start_ms = None
        self._loop_end_ms = None

    def _on_playback_position_changed(self, position_ms: int) -> None:
        if (
            self._loop_enabled
            and self._loop_start_ms is not None
            and self._loop_end_ms is not None
            and self._loop_end_ms > self._loop_start_ms
        ):
            if position_ms >= self._loop_end_ms:
                was_playing = self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
                self.seek(self._loop_start_ms / 1000.0)
                if was_playing:
                    self._player.play()

    def _on_position_changed_during_span(self, position_ms: int) -> None:
        if self._span_end_ms is not None and position_ms >= self._span_end_ms:
            self.pause()
            self._player.positionChanged.disconnect(self._on_position_changed_during_span)
            self._span_end_ms = None
