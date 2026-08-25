# preprocessing/global_relevance.py
"""
Global Investor Relevance Evaluation Engine (V2 - Hybrid: Rules + Kiwi TF-IDF Semantic Anchor)
Combines explicit signal matching with Kiwi Morphological TF-IDF Semantic Anchor similarity.
100% pure Python / scikit-learn / Kiwi without PyTorch DLL dependencies.
"""
import re
from typing import Dict, Any, List, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from kiwipiepy import Kiwi

_kiwi = Kiwi()

def kiwi_tokenize(text: str) -> List[str]:
    """Tokenizes Korean text into nouns, roots, and numbers."""
    if not text:
        return []
    tokens = _kiwi.tokenize(text)
    return [t.form for t in tokens if t.tag in ['NNG', 'NNP', 'SN', 'SL', 'VV', 'VA'] and len(t.form) > 1]

# 1. Global Investor Semantic Anchor Corpus
GLOBAL_INVESTOR_ANCHOR_DOC = """
글로벌 해외 기관투자자 외국인투자자 핵심 기업가치 밸류에이션 
대규모 해외 수주 공급 계약 체결 납품 제작 어드밴스드 패키징 
분기 실적 영업이익 매출 EBITDA 어닝서프라이즈 가이던스 
글로벌 빅테크 파트너십 공급망 엔비디아 TSMC 애플 마이크로소프트 오픈AI 테라파워 웨스팅하우스 
DART 전자공시 설비투자 CapEx 수율 가동률 지배구조 개편 합병 분할 M&A 
미국 반도체법 보조금 체코 원전 수출 수출 통제 규제 리스크 ADR MSCI
"""

# 2. Common Global Capital Market & Foreign Media Signals
GLOBAL_MEDIA_IB = [
    "블룸버그", "Bloomberg", "로이터", "Reuters", "WSJ", "월스트리트저널", "FT", "파이낸셜타임스", 
    "CNBC", "골드만삭스", "Goldman Sachs", "모건스탠리", "Morgan Stanley", "JP모건", "JPMorgan", 
    "씨티", "Citi", "노무라", "Nomura", "CLSA", "HSBC", "맥쿼리", "Macquarie", "UBS", "바클레이스"
]

GLOBAL_CAPITAL_MACRO = [
    "ADR", "MSCI", "FTSE", "EBITDA", "CapEx", "영업이익", "분기 실적", "어닝서프라이즈", "가이던스",
    "지배구조", "합병", "분할", "M&A", "자사주 소각", "배당", "지분 매각", "블록딜", "외국인 지분율",
    "해외 수주", "공급 계약", "조원", "억달러", "달러($)", "수율", "가동률", "수주잔고"
]

# 3. Company-Specific Global Signals
COMPANY_GLOBAL_SIGNALS = {
    "SK하이닉스": {
        "bigtech_partners": [
            "엔비디아", "Nvidia", "NVIDIA", "TSMC", "애플", "Apple", "마이크로소프트", "Microsoft", "MS", 
            "오픈AI", "OpenAI", "구글", "Google", "AMD", "테슬라", "Tesla", "아마존", "AWS", "메타", "Meta", 
            "인텔", "Intel", "ASML", "마이크론", "Micron", "퀄컴", "Qualcomm"
        ],
        "geopolitics_fabs": [
            "미국 반도체법", "CHIPS Act", "반도체법 보조금", "보조금 확정", "미국 상무부", "DOC", "러몬도",
            "대중 수출 통제", "수출 규제", "인디애나", "웨스트라피엣", "패키징 공장", "어드밴스드 패키징",
            "용인 클러스터", "청주 M15X", "관세", "글로벌 공급망"
        ],
        "tech_products": [
            "HBM", "HBM3", "HBM3E", "HBM4", "CXL", "LPDDR5X", "1c D램", "321단", "낸드", "CoWoS",
            "고대역폭 메모리", "AI 가속기", "차세대 D램", "TSV", "MR-MUF"
        ]
    },
    "두산에너빌리티": {
        "global_partners": [
            "웨스팅하우스", "Westinghouse", "테라파워", "TerraPower", "엑스에너지", "X-energy", "뉴스케일", 
            "NuScale", "빌 게이츠", "Bill Gates", "GE", "지멘스", "Siemens", "프라마톰", "한전", "한수원", "팀코리아"
        ],
        "geopolitics_contracts": [
            "체코", "두코바니", "체코 원전", "폴란드", "퐁트누프", "베트남", "사우디", "루마니아", "UAE", "바라카",
            "미국 원자력규제위원회", "NRC", "소형모듈원자로", "SMR", "원전 수출", "가스터빈 수출", "원전 르네상스"
        ],
        "governance_capital": [
            "두산로보틱스", "합병", "분할합병", "지배구조 개편", "합병비율", "주식매수청구권", "금감원 정정요구",
            "수주잔고", "가스터빈 수주", "원자로 주기기", "블록딜"
        ]
    }
}

# 4. Local-Only Noise & Penalties
LOCAL_CSR_PATTERNS = [
    "장학금", "김장", "봉사활동", "헌혈", "성금", "기부", "동호회", "사내 체육대회", 
    "신입사원", "채용 설명회", "사진전", "공모전", "바자회", "벽화", "취약계층 지원"
]

LOCAL_POLITICS_GOSSIP = [
    "청문회 공방", "국정감사 증인", "여야 설전", "정치권", "사생활", "이혼 소송", "가정사"
]

LOCAL_MARKET_CHATTER = [
    "개미 순매수", "동학개미", "코스피 마감", "장중 시황", "특징주 급등", "테마주", "상한가", "급등주"
]

def calculate_anchor_similarity(text: str) -> float:
    """Calculates TF-IDF cosine similarity between article text and global anchor document."""
    try:
        tfidf = TfidfVectorizer(tokenizer=kiwi_tokenize)
        matrix = tfidf.fit_transform([GLOBAL_INVESTOR_ANCHOR_DOC, text])
        sim = cosine_similarity(matrix[0:1], matrix[1:2])[0][0]
        return round(float(sim), 3)
    except Exception:
        return 0.0

def evaluate_global_relevance(title: str, body: str, keyword: str) -> Dict[str, Any]:
    """
    Evaluates global investor relevance using a Hybrid Engine:
    Score = (Explicit Signals 50%) + (Kiwi TF-IDF Semantic Anchor Similarity 50%) - Penalties
    """
    full_text = f"{title}\n{body}"
    target_key = "SK하이닉스" if ("하이닉스" in keyword or "SK" in keyword) else "두산에너빌리티"
    
    # 1. Rule & Signal Score (0 ~ 50 pts)
    signal_score = 0
    signals_found = []
    penalties_found = []
    
    # Foreign Media & IB (+15 pts)
    matched_media = []
    for m in GLOBAL_MEDIA_IB:
        if m in title:
            signal_score += 15
            matched_media.append(f"[제목] {m}")
        elif m in body:
            signal_score += 8
            matched_media.append(f"[본문] {m}")
    if matched_media:
        signals_found.append({"category": "외신/글로벌IB 인용", "items": matched_media[:3], "score": min(signal_score, 15)})

    # Capital Market / Macro (+15 pts)
    matched_cap = []
    for c in GLOBAL_CAPITAL_MACRO:
        if c in title:
            signal_score += 10
            matched_cap.append(f"[제목] {c}")
        elif c in body:
            signal_score += 5
            matched_cap.append(f"[본문] {c}")
    if matched_cap:
        signals_found.append({"category": "자본시장/실적/수주", "items": matched_cap[:4], "score": min(len(matched_cap)*5, 15)})

    # Company Global Specific Signals (+20 pts)
    comp_sig = COMPANY_GLOBAL_SIGNALS.get(target_key, {})
    for category_name, kw_list in comp_sig.items():
        matched_kws = []
        for kw in kw_list:
            if kw in title:
                signal_score += 15
                matched_kws.append(f"[제목] {kw}")
            elif kw in body:
                signal_score += 7
                matched_kws.append(f"[본문] {kw}")
        if matched_kws:
            signals_found.append({"category": f"글로벌시그널({category_name})", "items": matched_kws[:4], "score": min(len(matched_kws)*7, 20)})

    norm_signal_score = min(50.0, float(signal_score))

    # 2. Semantic Anchor Similarity Score (0 ~ 50 pts)
    snippet = f"{title}. {body[:400]}"
    anchor_similarity = calculate_anchor_similarity(snippet)
    
    # Scale similarity (TF-IDF similarity typically 0.05 ~ 0.50 for anchor matching)
    # sim <= 0.05 -> 0 pts, sim >= 0.35 -> 50 pts
    scaled_sim = max(0.0, min(1.0, (anchor_similarity - 0.05) / 0.30))
    semantic_score = round(scaled_sim * 50.0, 1)

    # 3. Penalties (-30 ~ -40 pts)
    penalty_score = 0
    
    # CSR / Local Charity
    csr_matched = [p for p in LOCAL_CSR_PATTERNS if p in full_text]
    if csr_matched:
        penalty_score += 35
        penalties_found.append(f"국내 사내행사/CSR/장학금 ('{', '.join(csr_matched[:2])}') [-35점]")
        
    # Domestic Politics / Gossip
    gossip_matched = [p for p in LOCAL_POLITICS_GOSSIP if p in full_text]
    if gossip_matched and ("지배구조" not in title and "합병" not in title and "M&A" not in title):
        penalty_score += 25
        penalties_found.append(f"국내 정치권 공방/단순 가십 ('{', '.join(gossip_matched[:2])}') [-25점]")

    # Broad Domestic Stock Chatter
    chatter_matched = [p for p in LOCAL_MARKET_CHATTER if p in title]
    if chatter_matched:
        penalty_score += 25
        penalties_found.append(f"국내 단순 시황/테마주 패턴 ('{', '.join(chatter_matched[:2])}') [-25점]")

    # 4. Final Hybrid Score (0 ~ 100)
    raw_final_score = norm_signal_score + semantic_score - penalty_score
    final_score = round(max(0.0, min(100.0, raw_final_score)), 1)
    
    # Determination
    is_global_relevant = (final_score >= 40.0)
    
    if final_score >= 70.0:
        grade = "HIGH"
        grade_label = "🌟 HIGH (글로벌 투자자 최우선 브리핑 대상)"
    elif final_score >= 40.0:
        grade = "MEDIUM"
        grade_label = "🌐 MEDIUM (글로벌 투자 유의미 기사)"
    else:
        grade = "LOW"
        grade_label = "🇰🇷 LOW / LOCAL (국내 로컬성/단순 시황 기사)"
        
    # Summary Reason
    if is_global_relevant:
        top_items = []
        for s in signals_found:
            top_items.extend(s.get("items", []))
        summary_reason = f"[글로벌 유의미: {final_score}점] 앵커유사도 {anchor_similarity*100:.1f}% | 주요 시그널: {', '.join(top_items[:3])}"
    else:
        if penalties_found:
            summary_reason = f"[국내 로컬/감점: {final_score}점] 감점 요인: {', '.join(penalties_found[:2])}"
        else:
            summary_reason = f"[국내 로컬성: {final_score}점] 앵커유사도 {anchor_similarity*100:.1f}% (글로벌 투자 시그널 미달)"

    return {
        "global_score": final_score,
        "is_global_relevant": is_global_relevant,
        "anchor_similarity": anchor_similarity,
        "semantic_score": semantic_score,
        "signal_score": norm_signal_score,
        "grade": grade,
        "grade_label": grade_label,
        "signals_found": signals_found,
        "penalties_found": penalties_found,
        "global_summary": summary_reason
    }
