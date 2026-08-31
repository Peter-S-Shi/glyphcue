from glyphcue.application.text_similarity import character_similarity


def test_identical_strings_are_fully_similar():
    assert character_similarity("hello", "hello") == 1.0


def test_completely_different_strings_of_equal_length_score_zero():
    assert character_similarity("abc", "xyz") == 0.0


def test_similarity_is_one_minus_normalized_edit_distance():
    # "kitten" -> "sitting" is the textbook edit-distance-3 example
    # (independent of this implementation), max length 7 -> 1 - 3/7.
    assert character_similarity("kitten", "sitting") == 1 - 3 / 7


def test_both_empty_strings_are_fully_similar():
    assert character_similarity("", "") == 1.0


def test_one_empty_string_scores_zero_against_nonempty():
    assert character_similarity("", "hello") == 0.0
    assert character_similarity("hello", "") == 0.0


def test_similarity_does_not_use_whitespace_tokenization():
    # A single missing space is a 1-character edit, not a completely
    # different "token sequence" -- proves comparison is character-level.
    assert character_similarity("hello world", "helloworld") == 1 - 1 / 11


def test_cjk_text_with_no_spaces_is_compared_correctly():
    # No whitespace at all; identical Chinese strings must be fully similar.
    assert character_similarity("今天天气非常好", "今天天气非常好") == 1.0


def test_cjk_text_with_one_character_difference_is_mostly_similar():
    # One character swapped out of 7 -> edit distance 1.
    assert character_similarity("今天天气非常好", "今天天气非常坏") == 1 - 1 / 7


def test_japanese_text_with_no_spaces_is_compared_correctly():
    assert character_similarity("今日はとても良い天気ですね", "今日はとても良い天気ですね") == 1.0
