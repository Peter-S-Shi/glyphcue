from glyphcue.ui.audio_chime import _synthesize_hotel_bell_wav, play_ocr_completion_chime


def test_synthesize_hotel_bell_wav():
    wav_data = _synthesize_hotel_bell_wav()
    assert isinstance(wav_data, bytes)
    assert len(wav_data) > 1000
    assert wav_data.startswith(b"RIFF")


def test_play_ocr_completion_chime_does_not_raise():
    # Verify fail-soft execution
    play_ocr_completion_chime()
