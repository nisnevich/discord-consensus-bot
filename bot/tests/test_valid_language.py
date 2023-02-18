import unittest

import nltk
from nltk.corpus import words

from bot.config.const import NLTK_DATASETS_DIR
from bot.utils.validation import is_valid_language


class TestIsValidLanguage(unittest.TestCase):
    def setUp(self):
        nltk.download('words', download_dir=NLTK_DATASETS_DIR)
        self.english_words = set(word.lower() for word in words.words())

    def test_only_non_english_words(self):
        text = "hola como estas"
        threshold = 0.5
        result = is_valid_language(text, threshold)
        self.assertFalse(result)

    def test_both_english_and_non_english_words(self):
        text = "hello hola como estas"
        threshold = 0.5
        result = is_valid_language(text, threshold)
        self.assertFalse(result)

    def test_more_than_50_percent_english_words(self):
        text = "hello hola como estas good morning"
        threshold = 0.5
        result = is_valid_language(text, threshold)
        self.assertTrue(result)

    def test_less_than_50_percent_english_words(self):
        text = "hola como estas good morning"
        threshold = 0.5
        result = is_valid_language(text, threshold)
        self.assertFalse(result)

    def test_exactly_50_percent_english_words(self):
        text = "hello hola"
        threshold = 0.5
        result = is_valid_language(text, threshold)
        self.assertTrue(result)

    def test_different_thresholds(self):
        text = "hello hola como estas good morning"
        threshold = 0.3
        result = is_valid_language(text, threshold)
        self.assertTrue(result)

        threshold = 0.4
        result = is_valid_language(text, threshold)
        self.assertTrue(result)

        threshold = 0.6
        result = is_valid_language(text, threshold)
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
