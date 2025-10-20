"""
OCR Abstraction Layer

This module provides a unified interface for different OCR engines.
"""
import pytesseract
from config import OCR_ENGINE, LANG_CODE_MAP

class OcrError(Exception):
    """Custom exception for OCR-related errors."""
    pass

class TesseractOcrEngine:
    """OCR engine implementation using Tesseract."""

    def image_to_data(self, image, lang_code: str) -> dict:
        """Performs OCR on an image and returns detailed data about each word."""
        tesseract_lang = LANG_CODE_MAP.get(lang_code, lang_code)
        try:
            return pytesseract.image_to_data(image, lang=tesseract_lang, output_type=pytesseract.Output.DICT)
        except pytesseract.pytesseract.TesseractError as e:
            print(f"Tesseract Error: {e}")
            # Re-raise as a generic OcrError for the worker to catch
            raise OcrError(f"Tesseract Error for language '{tesseract_lang}'. Please ensure the language data is installed.") from e

    def image_to_string(self, image, lang_code: str) -> str:
        """Performs OCR on an image and returns the recognized text as a single string."""
        tesseract_lang = LANG_CODE_MAP.get(lang_code, lang_code)
        try:
            return pytesseract.image_to_string(image, lang=tesseract_lang)
        except pytesseract.pytesseract.TesseractError as e:
            print(f"Tesseract Error: {e}")
            raise OcrError(f"Tesseract Error for language '{tesseract_lang}'.") from e


# --- Factory Function ---

def get_ocr_engine():
    """Factory function to get the configured OCR engine instance."""
    if OCR_ENGINE == 'tesseract':
        return TesseractOcrEngine()
    # elif OCR_ENGINE == 'paddle':
    #     return PaddleOcrEngine() # To be implemented
    else:
        raise ValueError(f"Unknown OCR engine specified in config: {OCR_ENGINE}")
