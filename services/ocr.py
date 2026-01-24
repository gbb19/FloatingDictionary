"""
OCR Abstraction Layer

This module provides a unified interface for different OCR engines.
"""

import pytesseract
from PIL.Image import Image

from config import AUTO_DETECT_LANGUAGES, LANG_CODE_MAP, OCR_ENGINE
from utils.app_logger import debug_print

# --- Base Classes & Exceptions ---


class OcrError(Exception):
    """Custom exception for OCR-related errors."""

    pass


class OcrEngine:
    """Abstract base class for OCR engines."""

    def image_to_data(self, image: Image, lang_code: str, config: str = "") -> dict:
        raise NotImplementedError

    def image_to_string(self, image: Image, lang_code: str, config: str = "") -> str:
        raise NotImplementedError


# --- Tesseract Implementation ---


class TesseractOcrEngine(OcrEngine):
    """OCR engine implementation using Tesseract."""

    def _get_tesseract_lang_string(self, lang_code: str) -> str:
        """
        Determines the language string for Tesseract.
        For 'auto', it prioritizes 'eng' then falls back to others for better performance.
        """
        if lang_code == "auto":
            # By default, try English first as it's common and fast.
            # If the calling logic needs to re-run, it can specify a different language.
            # For now, we combine them as the original logic did, but this is a point of optimization.
            return "+".join(AUTO_DETECT_LANGUAGES)
        return LANG_CODE_MAP.get(lang_code, lang_code)

    def image_to_data(self, image: Image, lang_code: str, config: str = "") -> dict:
        """
        Performs OCR and returns detailed data including bounding boxes.
        """
        tesseract_lang = self._get_tesseract_lang_string(lang_code)

        try:
            return pytesseract.image_to_data(
                image,
                lang=tesseract_lang,
                output_type=pytesseract.Output.DICT,
                config=config,
            )
        except pytesseract.pytesseract.TesseractError as e:
            debug_print(f"Tesseract Error: {e}")
            raise OcrError(
                f"Tesseract Error for lang '{tesseract_lang}'. Is the language data installed?"
            ) from e

    def image_to_string(self, image: Image, lang_code: str, config: str = "") -> str:
        tesseract_lang = self._get_tesseract_lang_string(lang_code)

        try:
            return pytesseract.image_to_string(
                image, lang=tesseract_lang, config=config
            )
        except pytesseract.pytesseract.TesseractError as e:
            debug_print(f"Tesseract Error: {e}")
            raise OcrError(f"Tesseract Error for lang '{tesseract_lang}'.") from e


# --- Factory Function ---


def get_ocr_engine():
    """Factory function to get the configured OCR engine instance."""
    if OCR_ENGINE == "tesseract":
        return TesseractOcrEngine()
    # elif OCR_ENGINE == 'paddle':
    #     return PaddleOcrEngine() # To be implemented
    else:
        raise ValueError(f"Unknown OCR engine specified in config: {OCR_ENGINE}")
