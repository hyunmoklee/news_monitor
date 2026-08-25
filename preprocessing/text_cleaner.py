# preprocessing/text_cleaner.py
import re
import html
from typing import Tuple, Dict, Any

def clean_text(raw_text: str, title: str = "", media_name: str = "") -> Tuple[str, Dict[str, Any]]:
    """
    [Stage 3.1: Universal Anchor-based High-Precision Text Cleaning]
    Extracts purely the editorial news article body by slicing between headline/byline start anchors
    and copyright/footer end anchors, completely stripping site navigations, unrelated article lists, and ads.
    """
    if not raw_text:
        return "", {"removed_patterns": [], "original_length": 0, "cleaned_length": 0, "has_noise": False}
        
    original_length = len(raw_text)
    removed_items = []
    has_noise = False
    
    cleaned = html.unescape(raw_text)
    
    # 1. Start Anchor: Find main headline or journalist byline
    start_pos = 0
    clean_title_snippet = re.sub(r'[^\w\s]', '', title)[:12].strip()
    
    if clean_title_snippet:
        t_match = re.search(r'#+\s*' + re.escape(clean_title_snippet), re.sub(r'[^\w\s#\n]', '', cleaned))
        if not t_match and len(title) >= 8:
            t_match = re.search(r'#+\s*' + re.escape(title[:8]), cleaned)
            
        if t_match:
            start_pos = t_match.end()
            has_noise = True
            removed_items.append("상단 웹 내비게이션/타이틀 이전 헤더 절삭")
        else:
            byline_match = re.search(r'[가-힣]{2,5}\s*(?:기자|특파원)\s*(?:=|\[|\(|\-)', cleaned)
            if byline_match and byline_match.start() > 200:
                start_pos = byline_match.start()
                has_noise = True
                removed_items.append("상단 바이라인 이전 웹 메뉴 절삭")
                
    extracted = cleaned[start_pos:]
    
    # 2. End Anchor: Cut off everything at the start of footers/best articles/comments
    end_patterns = [
        r'\n\s*###\s*\[?관련키워드\]?',
        r'\n\s*<저작권자',
        r'\n\s*\[저작권자',
        r'\n\s*저작권자\s*©',
        r'\n\s*Copyright\s*©',
        r'\n\s*###\s*\[?뉴스핌\s*베스트\s*기사',
        r'\n\s*###\s*\[?인기기사',
        r'\n\s*###\s*GAM\s*-',
        r'\n\s*디지털뉴스콘텐츠\s*이용규칙',
        r'\n\s*한국신문윤리위원회',
        r'\n\s*기자의\s*다른\s*기사\s*보기',
        r'\n\s*무단전재\s*및\s*재배포\s*금지',
        r'\n\s*무단전재-재배포\s*금지'
    ]
    for ep in end_patterns:
        m = re.search(ep, extracted, flags=re.IGNORECASE)
        if m:
            extracted = extracted[:m.start()]
            has_noise = True
            removed_items.append("하단 푸터/추천기사/저작권 이하 영역 절삭")
            break
            
    # 3. Clean inline artifacts and noisy markup
    extracted = re.sub(r'#+\s*※.*?\n', '', extracted)
    extracted = re.sub(r'기사입력\s*:.*?\n', '', extracted)
    extracted = re.sub(r'최종수정\s*:.*?\n', '', extracted)
    extracted = re.sub(r'\*\s*카카오톡;.*?\n', '', extracted)
    extracted = re.sub(r'--\s*선택\s*--\s*닫기', '', extracted)
    extracted = re.sub(r'###\s*AI\s*핵심\s*요약.*?!AI가\s*자동\s*생성한\s*요약으로\s*정확하지\s*않을\s*수\s*있어요\.', '', extracted, flags=re.DOTALL)
    extracted = re.sub(r'!\[.*?\]\(.*?\)|\[\]\(.*?\)', '', extracted)
    extracted = re.sub(r'\[(?:사진|자료사진|사진출처|그래픽)=[^\]]{2,30}\]', '', extracted)
    extracted = re.sub(r'\((?:사진|자료사진|사진출처|그래픽)=[^)]{2,30}\)', '', extracted)
    extracted = re.sub(r'\(?[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\)?', '', extracted)
    extracted = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', extracted)
    extracted = re.sub(r'^[^\n]*?(?:홈\s*경제|가\s*가\s*프린트|ry_cd=\d+)[^\n]*\n', '', extracted, flags=re.MULTILINE)
    
    # 4. Remove empty lines and non-article bullet items
    lines = []
    for l in extracted.splitlines():
        l_str = l.strip()
        if not l_str:
            continue
        if l_str.startswith('*') or l_str.startswith('#') or l_str.startswith('|'):
            continue
        if len(l_str) < 5 and not l_str.endswith('.'):
            continue
        if any(ign in l_str for ign in ['가 가 프린트', 'ry_cd=', '홈 경제']):
            continue
        lines.append(l_str)
        
    final_cleaned = "\n\n".join(lines)
    
    korean_chars = len(re.findall(r'[가-힣]', final_cleaned))
    total_chars = max(len(final_cleaned), 1)
    purity = round(korean_chars / total_chars, 2)
    
    clean_audit_log = {
        "original_length": original_length,
        "cleaned_length": len(final_cleaned),
        "korean_purity": purity,
        "has_noise": has_noise,
        "removed_items": removed_items
    }
    
    return final_cleaned, clean_audit_log
