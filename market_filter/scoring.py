"""
Step 2: 시황 스코어링 엔진.
- Aho-Corasick + Longest-First 조사 기반 어절 경계(Word Boundary) 검증
- MAX_POSTPOSITION_LEN 동적 상수화
- Cap 먼저(Max +50) -> F4 발동 시 50% Decay 적용
- F3 세분화: 제목 내 타깃 출현 시 -30점, 제목 부재 & 리드 200자 내 출현 시 -10점
"""
import re
from typing import List, Dict, Tuple, Set

RAW_POSTPOSITIONS = [
    "에서는", "에서도", "에게서", "에서", "에게", "부터", "까지", "처럼", 
    "조차", "마저", "이나", "이다", "였다", "이고", "이며", "으로", 
    "은", "는", "이", "가", "을", "를", "의", "에", "도", "와", "과", "등", "주", "株", "만", "로", "나"
]
KOREAN_POSTPOSITIONS = tuple(sorted(RAW_POSTPOSITIONS, key=len, reverse=True))
MAX_POSTPOSITION_LEN = max(len(p) for p in RAW_POSTPOSITIONS)

BOUNDARY_DELIMITERS = set(" \t\n\r.,!?\'\"()[]{}<>~·-")

def validate_word_boundary(text: str, start: int, end: int) -> Tuple[bool, str]:
    if start > 0 and text[start - 1] not in BOUNDARY_DELIMITERS:
        return False, "left_boundary_failed"
    
    if end < len(text):
        next_char = text[end]
        if next_char not in BOUNDARY_DELIMITERS:
            remainder = text[end : end + MAX_POSTPOSITION_LEN]
            matched_post = False
            for post in KOREAN_POSTPOSITIONS:
                if remainder.startswith(post):
                    after_post_idx = end + len(post)
                    if after_post_idx >= len(text) or text[after_post_idx] in BOUNDARY_DELIMITERS:
                        matched_post = True
                        break
            if not matched_post:
                return False, f"invalid_suffix_or_continuation({remainder})"
                
    return True, "valid_boundary"

def check_proximity_keywords(
    text: str, 
    match_start: int, 
    match_end: int, 
    keywords: List[str], 
    window_words: int = 5
) -> bool:
    left_text = text[:match_start].strip()
    right_text = text[match_end:].strip()
    
    left_words = left_text.split()[-window_words:] if left_text else []
    right_words = right_text.split()[:window_words] if right_text else []
    
    surrounding_text = " ".join(left_words + right_words)
    return any(kw in surrounding_text for kw in keywords)

def calculate_market_score(
    title: str, 
    body: str, 
    config: Dict, 
    company_list: List[str],
    rejected_logger = None
) -> Tuple[int, Dict]:
    weights = config.get("weights", {})
    w_f1 = weights.get("F1_title_market_regex", 40)
    w_f2_unit = weights.get("F2_stock_density_unit", 10)
    w_f2_cap = weights.get("F2_stock_density_cap", 50)
    w_f2_words = weights.get("F2_proximity_words", 5)
    w_f3 = weights.get("F3_lead_target_mention", -30)
    w_f4 = weights.get("F4_business_keyword_match", -30)
    decay_ratio = weights.get("F4_decay_ratio", 0.5)
    
    targets = config.get("targets", {})
    t_name = list(targets.keys())[0] if targets else "두산에너빌리티"
    t_info = targets.get(t_name, {})
    t_aliases = t_info.get("aliases", [t_name])
    t_biz_kws = t_info.get("business_keywords", [])
    
    market_patterns = config.get("market_jargon", {}).get("title_patterns", [])
    fluc_kws = config.get("market_jargon", {}).get("fluctuation_keywords", [])
    
    detail = {}
    
    # F1. 제목 시황 패턴 매칭
    f1_score = 0
    for pat in market_patterns:
        if re.search(pat, title):
            f1_score = w_f1
            break
    detail["F1_score"] = f1_score
    
    # F3. 위치 신호: 제목에 타깃 출현 시 -30, 리드 200자에만 출현 시 -10
    lead_200 = (body or "")[:200]
    has_target_title = any(a in title for a in t_aliases)
    has_target_lead = any(a in lead_200 for a in t_aliases)
    
    if has_target_title:
        f3_score = w_f3 # -30
    elif has_target_lead:
        f3_score = -10  # 약한 위치 신호
    else:
        f3_score = 0
    detail["F3_score"] = f3_score
    
    # F4. 비즈니스 고유 키워드 2종 이상 출현 검증
    matched_biz = [kw for kw in t_biz_kws if kw in (body or "")]
    is_f4_active = len(set(matched_biz)) >= 2
    f4_score = w_f4 if is_f4_active else 0
    detail["F4_score"] = f4_score
    detail["matched_biz_keywords"] = list(set(matched_biz))
    
    # F5. 실시간 시세봇 감지 (+40)
    f5_score = 0
    if re.search(r'장중\s*[\d,]+원|거래되고\s*있으며|지난\s*종가\s*대비|시가는\s*[\d,]+원|전일\s*대비\s*[\d.]+%|거래대금\s*[\d,]+', title + " " + lead_200):
        f5_score = 40
    detail["F5_score"] = f5_score

    # F6. [특징주], 테마주, ETF, 증시 풍향계 감지 (+30)
    f6_score = 0
    if re.search(r'\[특징주\]|특징주|[가-힣]+株|\[N2\s*증시|풍향계|ETF\s*강세', title):
        f6_score = 30
    detail["F6_score"] = f6_score

    # F7. 투자자 매매동향 나열 감지 (+30)
    f7_score = 0
    if re.search(r'1%\s*초고수|큰손들|고액자산가|개미들|순매수|갈아탔다', title):
        f7_score = 30
    detail["F7_score"] = f7_score

    # 타깃 기업 본사 언급 횟수 동적 계산
    target_mention_count = sum((body or "").count(a) for a in t_aliases)

    # F8. 그룹사/지주사/오너 동향 감지 (타깃 기업 본사 언급 1회 이하 + 그룹/지배구조 키워드) (+30)
    f8_score = 0
    if re.search(r'그룹사|지주사|지배구조|인물탐구|회장단|총수|오너\s*일가|M&A\s*후', title) and target_mention_count <= 1:
        f8_score = 30
    detail["F8_score"] = f8_score

    # F9. 지자체/광역단체 일반 행정·도정 감지 (타깃 기업 본사 언급 1회 이하 + 지자체 직제 키워드) (+30)
    f9_score = 0
    if re.search(r'도청|시청|도지사|광역단체장|특례시|도정\s*소식|재난통합', title) and target_mention_count <= 1:
        f9_score = 30
    detail["F9_score"] = f9_score


    # F2. 타 상장사 나열도
    valid_company_matches = 0
    for comp in company_list:
        for m in re.finditer(re.escape(comp), body or ""):
            s, e = m.start(), m.end()
            is_valid, reason = validate_word_boundary(body, s, e)
            if is_valid:
                if check_proximity_keywords(body, s, e, fluc_kws, window_words=w_f2_words):
                    valid_company_matches += 1
            else:
                if rejected_logger:
                    context = (body or "")[max(0, s-20) : min(len(body), e+20)]
                    rejected_logger.write(f"[REJECTED] Comp: {comp} | Context: {context} | Reason: {reason}\n")
                    
    # Cap 먼저 적용 -> F4 발동 시 Decay 적용
    raw_f2 = valid_company_matches * w_f2_unit
    capped_f2 = min(raw_f2, w_f2_cap)
    final_f2 = int(capped_f2 * decay_ratio) if is_f4_active else capped_f2
    detail["F2_raw_matches"] = valid_company_matches
    detail["F2_capped"] = capped_f2
    detail["F2_score"] = final_f2
    
    total_score = f1_score + final_f2 + f3_score + f4_score + f5_score + f6_score + f7_score + f8_score + f9_score
    detail["total_score"] = total_score
    
    return total_score, detail

