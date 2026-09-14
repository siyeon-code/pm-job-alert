# -*- coding: utf-8 -*-
"""
3단계: 공고 목록을 조건에 맞게 거르고, 슬랙 섹션별로 나누는 스크립트

규칙 (값은 config.py에서 수정)
  1) 제목에 제외 키워드가 있으면 버림
  2) 파견이면 버림 (사람인: 고용형태 코드 6 / 인크루트: 파견대행 피드 또는 제목에 '파견')
  3) 직무 분류 (공고 제목 기준, 띄어쓰기·대소문자 무시)
     - 기획 계열 + 인턴·계약직                → 2번 "인턴 · 계약직"
     - 핵심 키워드, 또는 기획 계열 + 신입 계열  → 1번 "정규직 · 신입"
     - 확장·도메인 키워드                      → 3번 "확장 · 도메인"
     - 셋 다 아니면 버림
  4) 지역: 서울·경기
  5) 경력: 최소 경력 3년 이하 (신입·경력무관 포함, 연차 표기가 없으면 통과)
  6) 날짜: 오늘 마감이면 "오늘 마감", 최근 24시간 안에 등록됐으면 "새로 등록"
     (둘 다 해당하면 "오늘 마감"에만 넣음)

실행 방법
  python3 job_filter.py              # 인크루트 공고로 필터 결과 보기
  python3 job_filter.py --all-dates  # 날짜 조건을 빼고 나머지 규칙만 확인
"""
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import config
from incruit_rss import fetch_incruit_jobs

KST = ZoneInfo(config.TIMEZONE)

# 슬랙 분류(1~3번)와 섹션 이름
CATEGORY_CORE = "1. 정규직 · 신입"
CATEGORY_INTERN = "2. 인턴 · 계약직"
CATEGORY_EXTENDED = "3. 확장 · 도메인"
SECTION_DEADLINE = "오늘 마감"
SECTION_NEW = "새로 등록"
SECTION_ANY_DATE = "날짜 조건 무시"


def squeeze(text):
    """비교하기 쉽게 소문자로 바꾸고 띄어쓰기를 모두 없앰 ('서비스 기획' → '서비스기획')"""
    return re.sub(r"\s+", "", text).lower()


def has_keyword(title, keyword):
    """제목에 키워드가 들어 있는지 확인 (띄어쓰기·대소문자 무시)

    PM, PO, MD처럼 짧은 영어 키워드는 앞뒤에 영어 글자가 붙어 있지 않을 때만 인정함.
    그냥 찾으면 'development' 안의 pm, 'Portfolio' 안의 po까지 잡히기 때문.
    """
    if re.fullmatch(r"[A-Za-z]{1,3}", keyword):
        pattern = rf"(?<![A-Za-z]){re.escape(keyword)}(?![A-Za-z])"
        return re.search(pattern, title, re.IGNORECASE) is not None
    return squeeze(keyword) in squeeze(title)


def find_keywords(title, keywords):
    """제목에 들어 있는 키워드만 골라서 돌려줌 ('서비스 기획'과 '서비스기획'은 하나로 침)"""
    found = []
    seen = set()
    for keyword in keywords:
        if squeeze(keyword) not in seen and has_keyword(title, keyword):
            found.append(keyword)
            seen.add(squeeze(keyword))
    return found


def min_career_years(career):
    """경력 표기에서 최소 경력(년)을 꺼냄. 알 수 없으면 None

    '신입', '경력무관', '신입/경력(1년↑)' → 0
    '경력 2년↓', '경력 3년 이하'          → 0
    '경력 3년↑', '경력 3~7년'            → 3
    '경력' (연차 표기 없음)               → None
    """
    if "신입" in career or "무관" in career:
        return 0
    if re.search(r"\d+\s*년\s*(↓|이하)", career):
        return 0
    number = re.search(r"\d+", career)
    return int(number.group()) if number else None


def is_capital_area(location):
    """근무지에 서울·경기가 들어 있는지 확인"""
    return any(word in location for word in config.REGION_KEYWORDS)


def is_dispatch(job):
    """파견 공고인지 확인"""
    if set(job.get("job_type_codes", [])) & config.EXCLUDED_JOB_TYPE_CODES:
        return True
    if job.get("from_dispatch_feed"):
        return True
    return bool(find_keywords(job["title"], config.DISPATCH_TITLE_KEYWORDS))


def is_intern_or_contract(job):
    """인턴·계약직인지 확인 (사람인: 고용형태 코드 / 공통: 제목 키워드)"""
    codes = set(job.get("job_type_codes", []))
    # 정규직(1)이 함께 적힌 공고는 코드만으로는 인턴·계약직으로 보지 않음
    if codes & set(config.INTERN_CONTRACT_JOB_TYPE_CODES) and "1" not in codes:
        return True
    return bool(find_keywords(job["title"], config.INTERN_KEYWORDS + config.CONTRACT_KEYWORDS))


def date_section(job, now):
    """오늘 마감이면 '오늘 마감', 최근 N시간 안에 등록됐으면 '새로 등록', 둘 다 아니면 None"""
    if job.get("deadline") == now.date():
        return SECTION_DEADLINE
    since = now - timedelta(hours=config.NEW_POSTING_WINDOW_HOURS)
    if job.get("posted_at"):  # 사람인: 등록 시각까지 알 수 있음
        if job["posted_at"] >= since:
            return SECTION_NEW
    elif job.get("posted_date"):  # 인크루트: 등록 날짜만 알 수 있어서 날짜로 비교
        if job["posted_date"] >= since.date():
            return SECTION_NEW
    return None


def classify(job, now, check_dates=True):
    """공고 1건을 검사해서 (통과한 공고, None) 또는 (None, 버린 이유)를 돌려줌"""
    # 공공기관처럼 수집 단계에서 코드로 이미 거른 공고는 분류가 정해져 있어서 날짜만 판단
    if job.get("fixed_category"):
        section = date_section(job, now)
        if check_dates and section is None:
            return None, "오늘 마감·새로 등록 아님"
        result = dict(job)
        result["category"] = job["fixed_category"]
        result["section"] = section if check_dates else SECTION_ANY_DATE
        result["matched"] = job.get("matched", [])
        return result, None

    title = job["title"]

    excluded = find_keywords(title, config.EXCLUDE_KEYWORDS)
    if excluded:
        return None, "제외 키워드"
    if is_dispatch(job):
        return None, "파견"

    # 직무 분류: 인턴·계약직 → 정규직·신입 → 확장·도메인 순서로 판단
    core = find_keywords(title, config.CORE_KEYWORDS)
    extended = find_keywords(title, config.EXTENDED_KEYWORDS + config.DOMAIN_KEYWORDS)
    entry = find_keywords(title, config.ENTRY_KEYWORDS)
    planning_family = bool(core or extended) or config.PLANNING_FAMILY_WORD in title
    if planning_family and is_intern_or_contract(job):
        category = CATEGORY_INTERN
    elif core or (planning_family and entry):
        category = CATEGORY_CORE
    elif extended:
        category = CATEGORY_EXTENDED
    elif planning_family:
        return None, "기획 공고지만 핵심·확장·도메인·신입 키워드 없음"
    else:
        return None, "직무 키워드 없음"

    if not is_capital_area(job["location"]):
        return None, "지역이 서울·경기 아님"
    years = min_career_years(job["career"])
    if years is not None and years > config.MAX_CAREER_YEARS:
        return None, f"최소 경력 {config.MAX_CAREER_YEARS}년 초과"

    section = date_section(job, now)
    if check_dates and section is None:
        return None, "오늘 마감·새로 등록 아님"

    result = dict(job)
    result["category"] = category
    result["section"] = section if check_dates else SECTION_ANY_DATE
    intern = find_keywords(title, config.INTERN_KEYWORDS + config.CONTRACT_KEYWORDS)
    result["matched"] = core + extended + entry + intern  # 슬랙에서 어떤 키워드로 잡혔는지 보여주기용
    return result, None


def filter_jobs(jobs, now, check_dates=True):
    """여러 공고를 검사해서 (통과한 공고 목록, 버린 이유별 공고 목록)을 돌려줌"""
    kept = []
    dropped = defaultdict(list)
    for job in jobs:
        result, reason = classify(job, now, check_dates)
        if result:
            kept.append(result)
        else:
            dropped[reason].append(job)
    return kept, dropped


def main():
    check_dates = "--all-dates" not in sys.argv
    now = datetime.now(KST)
    print(f"기준 시각(KST): {now:%Y-%m-%d %H:%M} / 날짜 조건: {'적용' if check_dates else '무시'}\n")

    jobs, errors = fetch_incruit_jobs()
    kept, dropped = filter_jobs(jobs, now, check_dates)

    # 섹션(오늘 마감/새로 등록) 안에서 분류(1~3번)별로 묶어서 출력
    sections = [SECTION_DEADLINE, SECTION_NEW] if check_dates else [SECTION_ANY_DATE]
    for section in sections:
        print(f"[{section}]")
        for category in (CATEGORY_CORE, CATEGORY_INTERN, CATEGORY_EXTENDED):
            group = [job for job in kept if job["section"] == section and job["category"] == category]
            print(f"  {category} ({len(group)}건)")
            for job in group:
                print(f"    - {job['company']} | {job['title']}")
                print(f"      경력: {job['career']} / 지역: {job['location']}"
                      f" / 마감: {job['deadline_text']} / 키워드: {', '.join(job['matched'])}")
        print()

    print(f"통과 {len(kept)}건 / 전체 {len(jobs)}건")
    print("[버린 이유]")
    for reason, group in sorted(dropped.items(), key=lambda pair: -len(pair[1])):
        examples = " / ".join(job["title"][:30] for job in group[:3])
        print(f"  {reason}: {len(group)}건 (예: {examples})")
    for error in errors:
        print("에러:", error)


if __name__ == "__main__":
    main()
