"""
OCR Abstraction Layer

This module provides a unified interface for different OCR engines.
"""
import pytesseract
from config import OCR_ENGINE, LANG_CODE_MAP, AUTO_DETECT_LANGUAGES

# --- Base Classes & Exceptions ---

class OcrError(Exception):
    """Custom exception for OCR-related errors."""
    pass

class OcrEngine:
    """Abstract base class for OCR engines."""
    def image_to_data(self, image: Image, lang_code: str) -> dict:
        raise NotImplementedError

    def image_to_string(self, image: Image, lang_code: str) -> str:
        raise NotImplementedError

# --- Tesseract Implementation ---

class TesseractOcrEngine(OcrEngine):
    """OCR engine implementation using Tesseract."""
    def image_to_data(self, image: Image, lang_code: str) -> dict:
        if lang_code == 'auto':
            tesseract_lang = '+'.join(AUTO_DETECT_LANGUAGES)
        else:
            tesseract_lang = LANG_CODE_MAP.get(lang_code, lang_code)
        
        try:
            return pytesseract.image_to_data(image, lang=tesseract_lang, output_type=pytesseract.Output.DICT)
        except pytesseract.pytesseract.TesseractError as e:
            print(f"Tesseract Error: {e}")
            raise OcrError(f"Tesseract Error for lang '{tesseract_lang}'. Is the language data installed?") from e

    def image_to_string(self, image: Image, lang_code: str) -> str:
        if lang_code == 'auto':
            tesseract_lang = '+'.join(AUTO_DETECT_LANGUAGES)
        else:
            tesseract_lang = LANG_CODE_MAP.get(lang_code, lang_code)

        try:
            return pytesseract.image_to_string(image, lang=tesseract_lang)
        except pytesseract.pytesseract.TesseractError as e:
            print(f"Tesseract Error: {e}")
            raise OcrError(f"Tesseract Error for lang '{tesseract_lang}'.") from e


# --- Factory Function ---

def get_ocr_engine():
    """Factory function to get the configured OCR engine instance."""
    if OCR_ENGINE == 'tesseract':
        return TesseractOcrEngine()
    # elif OCR_ENGINE == 'paddle':
    #     return PaddleOcrEngine() # To be implemented
    else:
        raise ValueError(f"Unknown OCR engine specified in config: {OCR_ENGINE}")
