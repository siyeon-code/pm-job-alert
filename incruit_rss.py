# -*- coding: utf-8 -*-
"""
2단계(인크루트): 인크루트 공식 RSS를 읽어서 공고 목록으로 정리하는 스크립트

하는 일
  1) config.py에 적힌 RSS 피드를 읽음 (공고 상세 페이지는 접근하지 않음)
  2) 공고마다 회사명·제목·경력·지역·마감일·링크를 꺼내서 같은 모양의 dict로 만듦
  3) 여러 피드에 같은 공고가 있으면 하나로 합침

실행 방법
  python3 incruit_rss.py

공고 1건의 모양 (사람인도 같은 모양으로 맞출 예정)
  {
    "source": "인크루트",
    "id": "incruit-2609110002183",     # 중복 방지용 번호 (출처-공고번호)
    "company": "(주)엘지유플러스",
    "title": "2026년 하반기 LG유플러스 신입채용",
    "career": "신입",                  # 원문 표기 그대로
    "location": "서울, 경기, 인천",
    "deadline": date(2026, 9, 27),     # 채용시·상시 마감이면 None
    "deadline_text": "09/27(일)",
    "posted_date": date(2026, 9, 11),  # 공고번호 앞 6자리(YYMMDD)
    "job_type": None,                  # RSS에는 고용형태 정보가 없음
    "from_dispatch_feed": False,       # 파견대행 피드에도 있었는지
    "feeds": ["웹서비스기획"],          # 어느 피드에서 찾았는지
    "url": "https://job.incruit.com/jobdb_info/jobpost.asp?job=2609110002183",
  }
"""
import html
import re
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests

import config

KST = ZoneInfo(config.TIMEZONE)


def fetch_feed(params):
    """RSS 피드 1개를 받아서 <item> 목록을 돌려줌. 실패하면 RuntimeError를 냄"""
    try:
        response = requests.get(
            config.INCRUIT_RSS_URL,
            params=params,
            headers={"User-Agent": config.USER_AGENT},
            timeout=20,
        )
    except requests.RequestException as error:
        raise RuntimeError(f"네트워크 오류: {error}") from None
    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code}")
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as error:
        raise RuntimeError(f"RSS 형식 오류: {error}") from None
    return root.findall("./channel/item")


def text_of(item, tag):
    """<item> 안의 태그 글자를 꺼냄 (없으면 빈 문자열). &amp; 같은 표기도 풀어줌"""
    return html.unescape((item.findtext(tag) or "").strip())


def parse_description(description):
    """'▨ 경력 : 신입<br><br>▨ 지역 : |서울|경기' 같은 설명을 {'경력': '신입', '지역': '|서울|경기'}로 바꿈"""
    fields = {}
    for part in re.split(r"<br\s*/?>", description):
        match = re.match(r"\s*▨\s*([^:]+?)\s*:\s*(.*)", part)
        if match:
            fields[match.group(1)] = match.group(2).strip()
    return fields


def parse_deadline(text, today):
    """'09/27(일)'을 date(올해, 9, 27)로 바꿈. '채용시'·'상시'처럼 날짜가 없으면 None"""
    match = re.match(r"(\d{1,2})/(\d{1,2})", text)
    if not match:
        return None
    month, day = int(match.group(1)), int(match.group(2))
    try:
        deadline = date(today.year, month, day)
        # 12월에 1월 마감 공고를 보는 경우: 반년 넘게 지난 날짜면 내년으로 계산
        if deadline < today - timedelta(days=180):
            deadline = date(today.year + 1, month, day)
    except ValueError:  # 2월 30일처럼 없는 날짜
        return None
    return deadline


def parse_posted_date(job_number):
    """공고번호 앞 6자리(YYMMDD)로 등록일을 만듦. '2609110002183' → date(2026, 9, 11)"""
    try:
        return datetime.strptime(job_number[:6], "%y%m%d").date()
    except ValueError:
        return None


def plain_company(name):
    """비교용 회사명: (주)·㈜·주식회사·(유)와 띄어쓰기를 뺌. '(주)베어로보틱스코리아' → '베어로보틱스코리아'"""
    return re.sub(r"\(주\)|㈜|주식회사|\(유\)|\s", "", name)


def clean_title(title, company):
    """'[회사명] 공고 제목'에서 앞의 [회사명]을 떼어냄

    회사명 표기가 조금 달라도 떼어냄: 회사 '(주)베어로보틱스코리아' + 제목 '[베어로보틱스코리아] PM' → 'PM'
    """
    match = re.match(r"\[([^\]]+)\]\s*", title)
    if match:
        inner = plain_company(match.group(1))
        if len(inner) >= 2 and inner in plain_company(company):
            return title[match.end():].strip()
    return title


def parse_item(item, today):
    """RSS <item> 1개를 공고 dict로 바꿈. 공고번호를 못 찾으면 None"""
    url = text_of(item, "link")
    number = re.search(r"job=(\d+)", url)
    if not number:
        return None
    fields = parse_description(text_of(item, "description"))
    company = text_of(item, "author") or fields.get("회사명", "")
    deadline_text = fields.get("마감일", "")
    regions = [region for region in fields.get("지역", "").split("|") if region]
    return {
        "source": "인크루트",
        "id": f"incruit-{number.group(1)}",
        "company": company,
        "title": clean_title(text_of(item, "title"), company),
        "career": fields.get("경력", ""),
        "location": ", ".join(regions),
        "deadline": parse_deadline(deadline_text, today),
        "deadline_text": deadline_text,
        "posted_date": parse_posted_date(number.group(1)),
        "job_type": None,
        "from_dispatch_feed": False,
        "feeds": [],
        "url": url,
    }


def fetch_incruit_jobs():
    """설정된 피드를 모두 읽어 (공고 목록, 에러 목록)을 돌려줌. 피드 하나가 실패해도 나머지는 계속 읽음"""
    today = datetime.now(KST).date()
    jobs = {}  # 공고 id → 공고 dict (같은 공고가 여러 피드에 있으면 하나로 합치려고 dict 사용)
    errors = []

    for feed_name, params in config.INCRUIT_FEEDS.items():
        try:
            items = fetch_feed(params)
        except RuntimeError as error:
            errors.append(f"인크루트 '{feed_name}' 피드: {error}")
            continue
        for item in items:
            job = parse_item(item, today)
            if job is None:
                continue
            job = jobs.setdefault(job["id"], job)  # 처음 본 공고면 등록, 이미 있으면 기존 것을 씀
            job["feeds"].append(feed_name)
        time.sleep(1)  # 사이트에 부담 주지 않게 피드 사이에 1초 쉬기

    # 파견대행 피드에도 있는 공고는 표시해 둠 (3단계에서 제외할 때 사용)
    try:
        for item in fetch_feed(config.INCRUIT_DISPATCH_FEED):
            job = parse_item(item, today)
            if job and job["id"] in jobs:
                jobs[job["id"]]["from_dispatch_feed"] = True
    except RuntimeError as error:
        errors.append(f"인크루트 파견대행 피드: {error}")

    return list(jobs.values()), errors


def main():
    if not config.USE_INCRUIT_RSS:
        print("config.py에서 USE_INCRUIT_RSS = False라서 인크루트는 읽지 않습니다.")
        return

    today = datetime.now(KST).date()
    print(f"기준 날짜(KST): {today}\n")
    jobs, errors = fetch_incruit_jobs()

    # 등록일 최신순으로 정렬 (등록일을 모르는 공고는 맨 뒤)
    jobs.sort(key=lambda job: job["posted_date"] or date.min, reverse=True)
    for job in jobs:
        dispatch = " [파견대행]" if job["from_dispatch_feed"] else ""
        print(f"- 등록 {job['posted_date']} | {job['company']} | {job['title']}{dispatch}")
        print(f"    경력: {job['career']} / 지역: {job['location'] or '표기 없음'}"
              f" / 마감: {job['deadline_text']} → {job['deadline']}")
        print(f"    피드: {', '.join(job['feeds'])} / {job['url']}")

    requests_sent = len(config.INCRUIT_FEEDS) + 1  # 직종 피드 + 파견대행 피드
    recent = [job for job in jobs if job["posted_date"] and job["posted_date"] >= today - timedelta(days=1)]
    print(f"\n총 {len(jobs)}건 (요청 {requests_sent}번) / 그중 어제·오늘 등록 {len(recent)}건")
    for error in errors:
        print("에러:", error)


if __name__ == "__main__":
    main()
