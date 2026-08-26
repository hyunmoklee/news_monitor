"""
SSOT (Single Source of Truth) 상장사 사전 로더.
타깃 기업 및 동의어/별칭을 명시적으로 배제하여 자기 언급 오탐을 원천 차단.
"""
import os
import yaml
from typing import List, Set

DEFAULT_KOSPI_KOSDAQ_TOP = [
    "삼성전자", "SK하이닉스", "LG에너지솔루션", "현대차", "기아", "셀트리온", 
    "삼성바이오로직스", "KB금융", "신한지주", "POSCO홀딩스", "NAVER", "카카오", 
    "현대모비스", "삼성물산", "삼성생명", "LG화학", "삼성SDI", "한화에어로스페이스", 
    "HD현대중공업", "메리츠금융지주", "하나금융지주", "우리금융지주", "HMM", 
    "한국전력", "KT&G", "크래프톤", "SK이노베이션", "엔씨소프트", "하이브", 
    "에코프로비엠", "에코프로", "HLB", "알테오젠", "삼천당제약", "리가켐바이오", 
    "휴젤", "클래시스", "펄어비스", "카카오게임즈", "CJ ENM", "스튜디오드래곤",
    "대상", "한샘", "신원", "대원", "효성", "풍산", "동아", "대한항공", "한화오션"
]

def load_config_targets(config_path: str = "market_filter_config.yaml") -> tuple:
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
            targets = cfg.get("targets", {})
            for t_name, t_info in targets.items():
                return t_name, t_info.get("aliases", [t_name])
    return "두산에너빌리티", ["두산에너빌리티", "두산", "에너빌리티", "두산에너빌", "두산중공업"]

def get_listed_companies(
    target_name: str = "두산에너빌리티", 
    target_aliases: List[str] = None,
    csv_path: str = "kospi_kosdaq_list.csv"
) -> List[str]:
    """
    상장사 사전을 로드하고, 타깃 기업 및 별칭을 완전히 제외한 리스트를 반환.
    """
    if target_aliases is None:
        _, target_aliases = load_config_targets()
    
    companies: Set[str] = set()
    
    if os.path.exists(csv_path):
        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                for line in f:
                    name = line.strip().split(",")[0].strip()
                    if name and len(name) >= 2:
                        companies.add(name)
        except Exception:
            companies = set(DEFAULT_KOSPI_KOSDAQ_TOP)
    else:
        companies = set(DEFAULT_KOSPI_KOSDAQ_TOP)
        
    exclude_set = set([target_name] + target_aliases)
    cleaned_companies = sorted(list(companies - exclude_set), key=len, reverse=True)
    return cleaned_companies
