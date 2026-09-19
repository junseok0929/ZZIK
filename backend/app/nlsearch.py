"""Rule-based Korean query understanding for album search.

This is deliberately a transparent keyword/date parser, not a language model or an
image-embedding semantic search. Every extracted condition is reported back to the
caller so the interface can show exactly what was understood and what was ignored.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from .analysis import SCENE_TAGS

# Korean words a member is likely to type mapped onto the stored scene tag vocabulary.
TAG_SYNONYMS = {
    '바다': '바다', '해변': '바다', '해수욕장': '바다', '바닷가': '바다', '해안': '바다', '오션': '바다',
    '물': '물', '호수': '물', '강': '물', '수영장': '물', '폭포': '물',
    '산': '산', '등산': '산', '산길': '산', '봉우리': '산', '봉우리길': '산', '계곡': '산',
    '음식': '음식', '먹부림': '음식', '맛집': '음식', '디저트': '음식', '빵': '음식', '회': '음식', '면': '음식',
    '음료': '음료', '커피': '카페', '카페': '카페', '카페투어': '카페',
    '식당': '식당', '레스토랑': '식당', '술집': '식당',
    '야경': '야경', '밤': '야경', '밤에': '야경', '야간': '야경', '조명': '야경',
    '노을': '노을', '석양': '노을', '일몰': '노을', '일출': '노을', '해돋이': '노을',
    '하늘': '하늘', '구름': '하늘',
    '꽃': '꽃', '벚꽃': '꽃', '꽃밭': '꽃',
    '자연': '자연', '나무': '자연', '풀': '자연', '들판': '자연', '정원': '자연',
    '숲': '숲', '숲길': '숲', '정글': '숲',
    '눈': '눈', '설경': '눈', '겨울풍경': '눈', '얼음': '눈',
    '비': '비', '우천': '비', '안개': '비',
    '도시': '도시', '시내': '도시', '도심': '도시',
    '건물': '건물', '건축': '건물', '호텔': '건물', '다리': '건물', '타워': '건물',
    '문화재': '문화재', '절': '문화재', '사찰': '문화재', '궁': '문화재', '성': '문화재', '박물관': '문화재', '교회': '문화재',
    '거리': '거리', '길거리': '거리', '골목': '거리', '산책로': '거리',
    '시장': '시장', '상점': '시장', '가게': '시장',
    '공원': '공원', '놀이공원': '공원', '놀이터': '공원',
    '이동': '이동', '배': '이동', '비행기': '이동', '공항': '이동', '기차': '이동', '기차역': '이동',
    '자동차': '이동', '자전거': '이동', '버스': '이동',
    '동물': '동물', '강아지': '동물', '고양이': '동물', '반려동물': '동물', '새': '동물',
    '실내': '실내', '방': '실내', '호텔방': '실내',
    '야외': '야외', '캠핑': '야외', '텐트': '야외', '등산로': '야외',
    '셀피': '셀피', '셀카': '셀피',
    '인물': '인물', '얼굴': '인물',
    '모임': '모임', '파티': '모임', '축제': '모임', '결혼식': '모임',
}
# Tag names themselves always resolve to the tag.
TAG_SYNONYMS.update({tag: tag for tag in SCENE_TAGS})

SEASONS = {'봄': (3, 5), '여름': (6, 8), '가을': (9, 11), '겨울': (12, 2)}
FILTER_WORDS = [
    (('최종본', '최종 사진', '확정본', '최종'), 'final'),
    (('확인 필요', '확인필요', '분석 실패', '실패한', '모르는 얼굴', '미확인'), 'review'),
    (('얼굴 없는', '얼굴없는', '얼굴 미검출', '사람 없는', '사람없는', '풍경만', '풍경 사진'), 'no_faces'),
    (('단체사진', '단체 사진', '단체', '다같이', '다 같이', '여러 명', '여러명', '함께 찍은', '같이 찍은'), 'group'),
    (('혼자', '혼자서', '솔로', '독사진', '개인사진', '개인 사진', '1인'), 'solo'),
]
RECOMMEND_WORDS = ('추천', '잘 나온', '잘나온', '베스트', '제일 좋은', '가장 좋은', 'ai 픽', 'ai픽', '골라줘', '괜찮은')
SELECTED_WORDS = ('고른 사진', '고른사진', '선택한 사진', '담아둔')
ALL_WORDS = ('모두', '다 나온', '다나온', '전원', '넷 다', '모두 나온', '전부')
ANY_WORDS = ('중 한 명', '중 한명', '누구든', '아무나', '한 명이라도', '한명이라도', '또는')


def _month_range(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    end = date(year + (month == 12), 1 if month == 12 else month + 1, 1) - timedelta(days=1)
    return start, end


def _clean(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


class Interpretation(dict):
    """A plain dict with the parsed conditions plus human-readable chips."""


def parse_query(query: str, people: list[dict] | None = None, *, locations: list[str] | None = None,
                labels: list[dict] | None = None, today: date | None = None) -> Interpretation:
    """Extract structured album filters from a Korean phrase.

    `people`, `locations` and `labels` are the album's own values, so a name only
    matches something that actually exists in this album.
    """
    original = query or ''
    remaining = ' ' + original.lower() + ' '
    today = today or date.today()
    chips: list[dict] = []
    result: Interpretation = Interpretation(people=[], match='all', filter='', tags=[], location='', label='',
                                            date_from='', date_to='', recommended=False, selected=False,
                                            text='', chips=chips, query=original)

    def consume(fragment: str) -> bool:
        nonlocal remaining
        if not fragment: return False
        needle = fragment.lower()
        if needle not in remaining: return False
        remaining = remaining.replace(needle, ' ')
        return True

    def chip(kind: str, label: str, value=None):
        chips.append({'kind': kind, 'label': label, 'value': value})

    # 1. People registered in this album; longest names first so "지수민" beats "지수".
    for person in sorted(people or [], key=lambda p: -len(p['name'])):
        if consume(person['name']):
            result['people'].append(person['id'])
            chip('person', person['name'], person['id'])

    # 2. Explicit place names already stored on this album's photos.
    for name in sorted({loc for loc in (locations or []) if loc}, key=len, reverse=True):
        if consume(name):
            result['location'] = name
            chip('location', name, name)
            break
    if not result['location']:
        # "제주에서", "부산서" style: take the stem before the locative particle.
        spot = re.search(r'([가-힣A-Za-z0-9]{2,20})(?:에서|에선|서)\s', remaining)
        if spot and spot.group(1) not in TAG_SYNONYMS:
            candidate = spot.group(1)
            for name in (locations or []):
                if name and candidate in name:
                    result['location'] = candidate
                    chip('location', candidate, candidate)
                    consume(spot.group(0).strip())
                    break

    # 3. Member labels.
    for label in sorted(labels or [], key=lambda l: -len(l['name'])):
        if consume(label['name']):
            result['label'] = label['id']
            chip('label', label['name'], label['id'])
            break

    # 4. Dates. Absolute expressions first, then relative ones.
    def set_range(start: date, end: date, text: str):
        if result['date_from']: return
        result['date_from'], result['date_to'] = start.isoformat(), end.isoformat()
        chip('date', text, [result['date_from'], result['date_to']])

    for pattern, build in (
        (r'(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일', lambda m: (date(int(m[1]), int(m[2]), int(m[3])),) * 2),
        (r'(\d{4})\s*[-./]\s*(\d{1,2})\s*[-./]\s*(\d{1,2})', lambda m: (date(int(m[1]), int(m[2]), int(m[3])),) * 2),
        (r'(\d{4})\s*년\s*(\d{1,2})\s*월', lambda m: _month_range(int(m[1]), int(m[2]))),
        (r'(\d{1,2})\s*월\s*(\d{1,2})\s*일', lambda m: (date(today.year, int(m[1]), int(m[2])),) * 2),
        (r'(\d{4})\s*년', lambda m: (date(int(m[1]), 1, 1), date(int(m[1]), 12, 31))),
        (r'(?<!\d)(\d{1,2})\s*월(?!\s*\d)', lambda m: _month_range(today.year, int(m[1]))),
    ):
        match = re.search(pattern, remaining)
        if not match: continue
        try: start, end = build(match)
        except ValueError: continue
        set_range(start, end, _clean(match.group(0)))
        consume(match.group(0))
        break

    if not result['date_from']:
        relatives = [
            ('그저께', lambda: (today - timedelta(days=2),) * 2), ('그제', lambda: (today - timedelta(days=2),) * 2),
            ('어제', lambda: (today - timedelta(days=1),) * 2), ('오늘', lambda: (today,) * 2),
            ('지난주', lambda: (today - timedelta(days=today.weekday() + 7), today - timedelta(days=today.weekday() + 1))),
            ('지난 주', lambda: (today - timedelta(days=today.weekday() + 7), today - timedelta(days=today.weekday() + 1))),
            ('이번 주', lambda: (today - timedelta(days=today.weekday()), today)),
            ('이번주', lambda: (today - timedelta(days=today.weekday()), today)),
            ('지난달', lambda: _month_range(today.year - (today.month == 1), 12 if today.month == 1 else today.month - 1)),
            ('지난 달', lambda: _month_range(today.year - (today.month == 1), 12 if today.month == 1 else today.month - 1)),
            ('이번 달', lambda: (date(today.year, today.month, 1), today)),
            ('이번달', lambda: (date(today.year, today.month, 1), today)),
            ('재작년', lambda: (date(today.year - 2, 1, 1), date(today.year - 2, 12, 31))),
            ('작년', lambda: (date(today.year - 1, 1, 1), date(today.year - 1, 12, 31))),
            ('지난해', lambda: (date(today.year - 1, 1, 1), date(today.year - 1, 12, 31))),
            ('올해', lambda: (date(today.year, 1, 1), today)),
        ]
        for word, build in relatives:
            if word in remaining:
                start, end = build()
                set_range(start, end, word)
                consume(word)
                break

    recent = re.search(r'최근\s*(\d{1,3})\s*일', remaining)
    if recent and not result['date_from']:
        days = max(1, min(365, int(recent.group(1))))
        set_range(today - timedelta(days=days - 1), today, _clean(recent.group(0)))
        consume(recent.group(0))

    for season, (start_month, end_month) in SEASONS.items():
        if season not in remaining: continue
        year = today.year - 1 if ('작년' in original or '지난' in original or today.month < start_month) else today.year
        if season == '겨울':
            start, end = date(year, 12, 1), _month_range(year + 1, 2)[1]
        else:
            start, end = date(year, start_month, 1), _month_range(year, end_month)[1]
        set_range(start, end, f'{year}년 {season}')
        consume(season)
        break

    # 5. Face-count and status words.
    count = re.search(r'(\d{1,2})\s*명', remaining)
    if count:
        wanted = int(count.group(1))
        if wanted == 1:
            result['filter'] = result['filter'] or 'solo'
            chip('filter', '혼자 나온 사진', 'solo')
        elif wanted > 1:
            result['face_count'] = wanted
            chip('face_count', f'{wanted}명 나온 사진', wanted)
        consume(count.group(0))

    for words, name in FILTER_WORDS:
        if result['filter']: break
        for word in words:
            if consume(word):
                result['filter'] = name
                chip('filter', {'final': '최종본', 'review': '확인 필요', 'no_faces': '얼굴 미검출',
                                'group': '2인 이상', 'solo': '혼자'}[name], name)
                break

    # 6. Scene tags, longest synonym first so "카페투어" is not read as "카페" plus leftovers.
    for word in sorted(TAG_SYNONYMS, key=len, reverse=True):
        if len(result['tags']) >= 4: break
        tag = TAG_SYNONYMS[word]
        if tag in result['tags']: continue
        if consume(word):
            result['tags'].append(tag)
            chip('tag', f'#{tag}', tag)

    # 7. Ranking and combination intent.
    for word in RECOMMEND_WORDS:
        if consume(word):
            result['recommended'] = True
            chip('recommended', 'AI 추천 순', True)
            break
    for word in SELECTED_WORDS:
        if consume(word):
            result['selected'] = True
            chip('selected', '함께 고른 사진', True)
            break
    if len(result['people']) > 1:
        if any(word in remaining or word in original for word in ANY_WORDS):
            result['match'] = 'any'
            chip('match', '선택한 사람 중 누구든', 'any')
        else:
            if any(word in original for word in ALL_WORDS):
                chip('match', '모두 함께 나온 사진', 'all')
            result['match'] = 'all'
    for word in ANY_WORDS + ALL_WORDS:
        consume(word)

    # 8. Whatever is left is a plain substring search over filename, memo, place and names.
    leftover = _clean(re.sub(r'[의를을이가와과랑하고에서에는은도만]?\s', ' ', remaining))
    leftover = _clean(re.sub(r'\b(사진|사진들|찍은|나온|보여줘|찾아줘|보고싶어|어디|있어|중에서|중에)\b', ' ', leftover))
    result['text'] = leftover if len(leftover) >= 2 else ''
    if result['text']: chip('text', f'"{result["text"]}" 포함', result['text'])
    result['matched'] = bool(chips)
    return result
