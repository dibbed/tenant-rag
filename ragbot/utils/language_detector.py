"""
Language Detection Utility
"""

import re


class LanguageDetector:
    """Simple language detector for Persian, English, and Arabic"""
    
    def __init__(self):
        # Persian Unicode range
        self.persian_pattern = re.compile(r'[\u0600-\u06FF]')
        # Arabic Unicode range (overlaps with Persian but includes Arabic-specific chars)
        self.arabic_pattern = re.compile(r'[\u0600-\u06FF\u0750-\u077F]')
        # English pattern
        self.english_pattern = re.compile(r'[a-zA-Z]')
    
    def detect(self, text: str) -> str:
        """
        Detect the primary language of the text
        
        Args:
            text: Input text to analyze
            
        Returns:
            Language code: 'fa', 'en', 'ar', or 'mixed'
        """
        if not text or not text.strip():
            return 'en'  # Default to English for empty text
        
        # Count characters for each language
        persian_chars = len(self.persian_pattern.findall(text))
        english_chars = len(self.english_pattern.findall(text))
        
        # Calculate percentages
        total_chars = len(text.replace(' ', ''))  # Exclude spaces
        if total_chars == 0:
            return 'en'
        
        persian_ratio = persian_chars / total_chars
        english_ratio = english_chars / total_chars
        
        # Determine primary language
        if persian_ratio > 0.3:
            if english_ratio > 0.3:
                return 'mixed'
            return 'fa'
        elif english_ratio > 0.3:
            return 'en'
        elif persian_chars > 0:
            return 'fa'
        else:
            return 'en'  # Default to English
    
    def is_rtl(self, text: str) -> bool:
        """Check if text is primarily right-to-left"""
        return self.detect(text) in ['fa', 'ar']
