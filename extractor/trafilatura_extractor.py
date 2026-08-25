# extractor/trafilatura_extractor.py
import logging
from typing import Dict, Any, Optional
import trafilatura

logger = logging.getLogger(__name__)

def extract_with_trafilatura(html: str, url: str = "") -> Dict[str, Any]:
    """
    Extracts article content using Trafilatura in both standard (recall-focused)
    and precision (precision-focused) modes, along with article metadata.

    Returns:
    {
        "standard": {"text": str, "length": int, "success": bool},
        "precision": {"text": str, "length": int, "success": bool},
        "metadata": {"title": str, "author": str, "date": str, "sitename": str}
    }
    """
    if not html or not html.strip():
        return {
            "standard": {"text": "", "length": 0, "success": False},
            "precision": {"text": "", "length": 0, "success": False},
            "metadata": {"title": "", "author": "", "date": "", "sitename": ""}
        }

    # 1. Standard mode extraction (favor_precision=False)
    standard_text = ""
    try:
        res_std = trafilatura.extract(
            html,
            url=url,
            favor_precision=False,
            include_links=False,
            include_images=False,
            include_comments=False,
            output_format="txt"
        )
        standard_text = (res_std or "").strip()
    except Exception as e:
        logger.warning(f"Trafilatura standard extraction error for {url}: {e}")

    # 2. Precision mode extraction (favor_precision=True)
    precision_text = ""
    try:
        res_prec = trafilatura.extract(
            html,
            url=url,
            favor_precision=True,
            include_links=False,
            include_images=False,
            include_comments=False,
            output_format="txt"
        )
        precision_text = (res_prec or "").strip()
    except Exception as e:
        logger.warning(f"Trafilatura precision extraction error for {url}: {e}")

    # 3. Metadata extraction
    meta_title = ""
    meta_author = ""
    meta_date = ""
    meta_sitename = ""
    try:
        meta = trafilatura.extract_metadata(html, default_url=url)
        if meta:
            meta_title = meta.title or ""
            meta_author = meta.author or ""
            meta_date = meta.date or ""
            meta_sitename = meta.sitename or ""
    except Exception as e:
        logger.debug(f"Trafilatura metadata extraction error for {url}: {e}")

    return {
        "standard": {
            "text": standard_text,
            "length": len(standard_text),
            "success": len(standard_text) > 0
        },
        "precision": {
            "text": precision_text,
            "length": len(precision_text),
            "success": len(precision_text) > 0
        },
        "metadata": {
            "title": meta_title,
            "author": meta_author,
            "date": meta_date,
            "sitename": meta_sitename
        }
    }
