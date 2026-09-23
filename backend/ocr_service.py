"""
OCR Service for DecisionFlow AI
Extracts readable text and data from uploaded image files (.png, .jpg, .jpeg, .webp).
Uses RapidOCR (local ONNX runtime) with fallback to native Windows OCR (winocr).
"""

import io
import logging
from typing import Optional
from PIL import Image

logger = logging.getLogger("decisionflow.ocr")

# Lazy-loaded RapidOCR engine instance
_rapid_ocr_engine = None


def get_rapid_ocr():
    global _rapid_ocr_engine
    if _rapid_ocr_engine is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _rapid_ocr_engine = RapidOCR()
            logger.info("RapidOCR engine initialized successfully.")
        except Exception as e:
            logger.warning("Could not initialize RapidOCR: %s", e)
            _rapid_ocr_engine = False
    return _rapid_ocr_engine if _rapid_ocr_engine is not False else None


def extract_text_from_image(image_bytes: bytes, filename: str = "image") -> str:
    """
    Extracts text from image bytes using RapidOCR or winocr fallback.
    Returns cleaned text string or empty string if no text detected.
    """
    if not image_bytes or len(image_bytes) == 0:
        return ""

    try:
        # Load and normalize image
        pil_image = Image.open(io.BytesIO(image_bytes))
        # Convert RGBA / P / L to RGB
        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")
    except Exception as e:
        logger.error("Failed to load image '%s' with PIL: %s", filename, e)
        raise ValueError(f"Invalid or corrupted image file: {filename}") from e

    extracted_lines = []

    # Attempt 1: RapidOCR (high accuracy, ONNX-based)
    rapid = get_rapid_ocr()
    if rapid:
        try:
            result, _ = rapid(pil_image)
            if result:
                for line in result:
                    # line format: [box, text, score]
                    text = str(line[1]).strip()
                    score = float(line[2])
                    if text and score >= 0.4:
                        extracted_lines.append(text)
                if extracted_lines:
                    text_result = "\n".join(extracted_lines)
                    logger.info("RapidOCR extracted %d lines from '%s'", len(extracted_lines), filename)
                    return text_result
        except Exception as e:
            logger.warning("RapidOCR extraction failed on '%s': %s. Trying winocr fallback...", filename, e)

    # Attempt 2: Native Windows OCR (winocr) fallback
    try:
        import asyncio
        import winocr

        async def _run_winocr():
            return await winocr.recognize_pil(pil_image, lang="en")

        # Handle running in existing event loop or fresh
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Running inside active loop (like FastAPI)
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    res = pool.submit(asyncio.run, _run_winocr()).result()
            else:
                res = loop.run_until_complete(_run_winocr())
        except Exception:
            res = asyncio.run(_run_winocr())

        if res and hasattr(res, "text") and res.text:
            text = str(res.text).strip()
            if text:
                logger.info("winocr fallback extracted %d chars from '%s'", len(text), filename)
                return text
    except Exception as e:
        logger.warning("winocr fallback also failed on '%s': %s", filename, e)

    return "\n".join(extracted_lines) if extracted_lines else ""
