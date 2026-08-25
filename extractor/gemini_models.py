# extractor/gemini_models.py
import os
from typing import List, Dict, Any, Optional

GEMINI_SUPPORTED_MODELS: List[Dict[str, Any]] = [
    {
        "id": "gemini-2.5-flash",
        "name": "Gemini 2.5 Flash",
        "recommended": True,
        "description": "최신 고속 경량 모델. 본문 정제 및 노이즈 제거 작업에 가장 추천됨.",
        "input_cost_per_1m": 0.075,
        "output_cost_per_1m": 0.30
    },
    {
        "id": "gemini-2.5-pro",
        "name": "Gemini 2.5 Pro",
        "recommended": False,
        "description": "최고 정밀도 추론 모델. 복잡한 구조 분석 및 고난도 본문 추출 시 활용.",
        "input_cost_per_1m": 1.25,
        "output_cost_per_1m": 5.00
    },
    {
        "id": "gemini-2.0-flash",
        "name": "Gemini 2.0 Flash",
        "recommended": False,
        "description": "2.0 세대 차세대 고속 모델.",
        "input_cost_per_1m": 0.10,
        "output_cost_per_1m": 0.40
    },
    {
        "id": "gemini-2.0-flash-lite",
        "name": "Gemini 2.0 Flash Lite",
        "recommended": False,
        "description": "초저비용 대량 정제 처리에 최적화된 초경량 모델.",
        "input_cost_per_1m": 0.0375,
        "output_cost_per_1m": 0.15
    },
    {
        "id": "gemini-1.5-flash",
        "name": "Gemini 1.5 Flash",
        "recommended": False,
        "description": "안정적인 1.5 세대 고속 모델 (하위 호환).",
        "input_cost_per_1m": 0.075,
        "output_cost_per_1m": 0.30
    },
    {
        "id": "gemini-1.5-pro",
        "name": "Gemini 1.5 Pro",
        "recommended": False,
        "description": "1.5 세대 고성능 모델.",
        "input_cost_per_1m": 1.25,
        "output_cost_per_1m": 5.00
    }
]

def list_available_gemini_models(api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    key = api_key or os.getenv("GEMINI_API_KEY", "")
    if not key:
        return GEMINI_SUPPORTED_MODELS

    try:
        from google import genai
        client = genai.Client(api_key=key)
        live_models = client.models.list()
        
        supported_ids = {m["id"] for m in GEMINI_SUPPORTED_MODELS}
        results = []
        for model in live_models:
            model_name = getattr(model, "name", str(model))
            clean_id = model_name.replace("models/", "")
            if clean_id in supported_ids:
                meta = next(item for item in GEMINI_SUPPORTED_MODELS if item["id"] == clean_id)
                results.append(meta)
        return results if results else GEMINI_SUPPORTED_MODELS
    except Exception:
        return GEMINI_SUPPORTED_MODELS
