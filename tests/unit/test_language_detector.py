"""
Tests for language detector functionality.
"""


from ragbot.utils.language_detector import LanguageDetector


class TestLanguageDetector:
    """Test language detector functionality."""
    
    def test_init(self):
        """Test LanguageDetector initialization."""
        detector = LanguageDetector()
        assert detector is not None
        assert hasattr(detector, 'persian_pattern')
        assert hasattr(detector, 'arabic_pattern')
        assert hasattr(detector, 'english_pattern')
    
    def test_detect_empty_text(self):
        """Test detection with empty text."""
        detector = LanguageDetector()
        assert detector.detect("") == "en"
        assert detector.detect("   ") == "en"
        assert detector.detect(None) == "en"
    
    def test_detect_persian_text(self):
        """Test detection of Persian text."""
        detector = LanguageDetector()
        
        # Pure Persian text
        persian_text = "سلام دنیا! این یک متن فارسی است."
        assert detector.detect(persian_text) == "fa"
        
        # Persian with some numbers
        persian_with_numbers = "سال ۱۴۰۳ سال خوبی است."
        assert detector.detect(persian_with_numbers) == "fa"
    
    def test_detect_english_text(self):
        """Test detection of English text."""
        detector = LanguageDetector()
        
        # Pure English text
        english_text = "Hello world! This is an English text."
        assert detector.detect(english_text) == "en"
        
        # English with numbers
        english_with_numbers = "The year 2024 is a good year."
        assert detector.detect(english_with_numbers) == "en"
    
    def test_detect_mixed_text(self):
        """Test detection of mixed Persian-English text."""
        detector = LanguageDetector()
        
        # Mixed text with significant Persian and English
        mixed_text = "Hello سلام! This is یک متن mixed است."
        assert detector.detect(mixed_text) == "mixed"
        
        # Another mixed example
        mixed_text2 = "Python programming زبان برنامه‌نویسی است."
        assert detector.detect(mixed_text2) == "mixed"
    
    def test_detect_persian_dominant(self):
        """Test detection when Persian is dominant."""
        detector = LanguageDetector()
        
        # Mostly Persian with little English
        persian_dominant = "این یک متن فارسی است که فقط یک کلمه English دارد."
        assert detector.detect(persian_dominant) == "fa"
    
    def test_detect_english_dominant(self):
        """Test detection when English is dominant."""
        detector = LanguageDetector()
        
        # Mostly English with little Persian
        english_dominant = "This is an English text with only one فارسی word."
        assert detector.detect(english_dominant) == "en"
    
    def test_detect_numbers_and_symbols(self):
        """Test detection with numbers and symbols."""
        detector = LanguageDetector()
        
        # Only numbers and symbols
        numbers_only = "123456789 !@#$%^&*()"
        assert detector.detect(numbers_only) == "en"
        
        # Persian numbers
        persian_numbers = "۱۲۳۴۵۶۷۸۹"
        assert detector.detect(persian_numbers) == "fa"
    
    def test_detect_whitespace_only(self):
        """Test detection with whitespace-only text."""
        detector = LanguageDetector()
        
        whitespace_text = "   \t\n   "
        assert detector.detect(whitespace_text) == "en"
    
    def test_detect_single_characters(self):
        """Test detection with single characters."""
        detector = LanguageDetector()
        
        # Single Persian character
        assert detector.detect("ا") == "fa"
        
        # Single English character
        assert detector.detect("a") == "en"
        
        # Single number
        assert detector.detect("1") == "en"
    
    def test_detect_arabic_text(self):
        """Test detection of Arabic text (should be detected as Persian)."""
        detector = LanguageDetector()
        
        # Arabic text (uses similar Unicode range)
        arabic_text = "مرحبا بالعالم"
        result = detector.detect(arabic_text)
        # Arabic should be detected as Persian due to Unicode overlap
        assert result == "fa"
    
    def test_is_rtl_persian(self):
        """Test RTL detection for Persian text."""
        detector = LanguageDetector()
        
        persian_text = "سلام دنیا"
        assert detector.is_rtl(persian_text) is True
    
    def test_is_rtl_english(self):
        """Test RTL detection for English text."""
        detector = LanguageDetector()
        
        english_text = "Hello world"
        assert detector.is_rtl(english_text) is False
    
    def test_is_rtl_mixed(self):
        """Test RTL detection for mixed text."""
        detector = LanguageDetector()
        
        # Mixed text should be RTL if detected as Persian
        mixed_persian = "سلام Hello دنیا"
        # This should be detected as mixed, but is_rtl checks for 'fa' or 'ar'
        assert detector.is_rtl(mixed_persian) is False
        
        # Mostly Persian should be RTL
        mostly_persian = "این یک متن فارسی است با یک کلمه English"
        assert detector.is_rtl(mostly_persian) is True
    
    def test_is_rtl_empty(self):
        """Test RTL detection for empty text."""
        detector = LanguageDetector()
        
        assert detector.is_rtl("") is False
        assert detector.is_rtl("   ") is False
    
    def test_detect_edge_cases(self):
        """Test detection with edge cases."""
        detector = LanguageDetector()
        
        # Very short Persian text
        short_persian = "سلام"
        assert detector.detect(short_persian) == "fa"
        
        # Very short English text
        short_english = "Hi"
        assert detector.detect(short_english) == "en"
        
        # Text with only punctuation
        punctuation_only = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        assert detector.detect(punctuation_only) == "en"
    
    def test_detect_threshold_behavior(self):
        """Test detection behavior around the 30% threshold."""
        detector = LanguageDetector()
        
        # Text with exactly around 30% Persian characters
        # This tests the threshold logic in the detect method
        text_30_percent = "سلام" + "hello world test"  # ~30% Persian
        result = detector.detect(text_30_percent)
        # Should be detected based on the exact ratio
        assert result in ["fa", "mixed"]
    
    def test_detect_unicode_edge_cases(self):
        """Test detection with Unicode edge cases."""
        detector = LanguageDetector()
        
        # Persian text with Arabic numerals
        persian_with_arabic_nums = "سال 2024 خوب است"
        assert detector.detect(persian_with_arabic_nums) == "fa"
        
        # English with Persian numerals
        english_with_persian_nums = "Year ۲۰۲۴ is good"
        result = detector.detect(english_with_persian_nums)
        assert result in ["en", "mixed"]  # Depends on character count
    
    def test_detect_long_text(self):
        """Test detection with longer text samples."""
        detector = LanguageDetector()
        
        # Long Persian text
        long_persian = "این یک متن طولانی فارسی است که برای تست عملکرد تشخیص زبان نوشته شده است. " * 10
        assert detector.detect(long_persian) == "fa"
        
        # Long English text
        long_english = "This is a long English text written to test the language detection functionality. " * 10
        assert detector.detect(long_english) == "en"
    
    def test_detect_special_characters(self):
        """Test detection with special Persian characters."""
        detector = LanguageDetector()
        
        # Persian text with special characters
        persian_special = "گچپژ‌ئ‌ء"
        assert detector.detect(persian_special) == "fa"
        
        # Persian text with ZWNJ (Zero Width Non-Joiner)
        persian_zwnj = "می‌خواهم"
        assert detector.detect(persian_zwnj) == "fa"
