# -*- coding: utf-8 -*-
"""
공공기관 채용정보 API(재정경제부, 공공데이터포털)에서 청년인턴 공고를 가져오는 스크립트

문서: https://www.data.go.kr/data/15125273/openapi.do (참고문서 "코드 정의서 v1.2")

하는 일
  1) 서울·경기 근무, 진행 중인 공고를 전부 받음 (보통 호출 1회)
     - API의 공고 시작일 검색 조건은 결과가 이상해서 쓰지 않고, 날짜는 3단계 필터에서 판단
     - 연결이 순간적으로 안 되면 몇 번 다시 시도함
  2) 아래 조건을 모두 만족하는 공고만 남김
     (공공기관 공고는 제목에 직무가 거의 안 나와서 제목 키워드 대신 코드로 거름)
     - 고용형태: 청년인턴 / 청년인턴(체험형) / 청년인턴(채용형)
     - 직무(NCS): 경영·회계·사무 또는 정보통신
     - 채용구분: 신입 또는 신입+경력
  3) 인크루트와 같은 모양의 공고 dict로 바꿈 (슬랙 2번 "인턴 · 계약직" 섹션으로 고정)

실행 방법
  python3 public_jobs.py
"""
import os
import time
from datetime import datetime

import requests

import config
from job_filter import CATEGORY_INTERN, KST, filter_jobs
from saramin_api import load_env_file

WEEKDAYS = "월화수목금토일"


def codes_of(text):
    """'R1050,R1060' → {'R1050', 'R1060'}"""
    return {code for code in (text or "").split(",") if code}


def parse_ymd(text):
    """'20260929' → date(2026, 9, 29). 형식이 다르면 None"""
    try:
        return datetime.strptime(text, "%Y%m%d").date()
    except (TypeError, ValueError):
        return None


def request_with_retry(params, service_key):
    """API를 호출함. 연결이 순간적으로 안 될 때를 대비해 정해진 횟수만큼 다시 시도"""
    last_error = None
    for attempt in range(1, config.PUBLIC_JOBS_RETRIES + 1):
        try:
            # timeout=(연결 대기 15초, 응답 대기 60초)
            return requests.get(config.PUBLIC_JOBS_API_URL, params=params, timeout=(15, 60))
        except requests.RequestException as error:
            last_error = error
            if attempt < config.PUBLIC_JOBS_RETRIES:
                time.sleep(config.PUBLIC_JOBS_RETRY_WAIT_SECONDS)
    # 에러 메시지에 키가 들어간 주소가 섞일 수 있어서 키를 가림
    message = str(last_error).replace(service_key, "****")
    raise RuntimeError(f"공공기관 API 네트워크 오류 ({config.PUBLIC_JOBS_RETRIES}번 시도): {message}")


def fetch_all_ongoing(service_key):
    """진행 중인 서울·경기 공고를 모두 받아 목록으로 돌려줌. 실패하면 RuntimeError를 냄"""
    items, page = [], 1
    while page <= config.PUBLIC_JOBS_MAX_PAGES:
        params = {
            "serviceKey": service_key,
            "resultType": "json",
            "ongoingYn": "Y",
            "workRgnLst": ",".join(config.PUBLIC_JOBS_REGION_CODES),  # 여러 코드는 쉼표 = "하나라도 해당"
            "numOfRows": config.PUBLIC_JOBS_PAGE_SIZE,
            "pageNo": page,
        }
        response = request_with_retry(params, service_key)
        try:
            data = response.json()
        except ValueError:
            # 인증키 오류 등은 JSON이 아닌 글자로 올 수 있음
            text = response.text[:200].replace(service_key, "****")
            raise RuntimeError(f"공공기관 API 응답 오류 (HTTP {response.status_code}): {text}") from None
        if str(data.get("resultCode")) != "200":
            raise RuntimeError(f"공공기관 API 에러 code={data.get('resultCode')} message={data.get('resultMsg')}")

        batch = data.get("result") or []
        items += batch
        if not batch or len(items) >= int(data.get("totalCount") or 0):
            break
        page += 1
    return items


def is_target(item):
    """청년인턴 + 경영·회계·사무/정보통신 + 신입 계열 공고인지 확인"""
    return bool(
        codes_of(item.get("hireTypeLst")) & set(config.PUBLIC_JOBS_INTERN_CODES)
        and codes_of(item.get("ncsCdLst")) & set(config.PUBLIC_JOBS_NCS_CODES)
        and item.get("recrutSe") in config.PUBLIC_JOBS_ENTRY_CODES
    )


def to_job(item):
    """API 항목 1개를 공통 공고 dict로 바꿈"""
    number = item["recrutPblntSn"]
    deadline = parse_ymd(item.get("pbancEndYmd"))
    hire_codes = codes_of(item.get("hireTypeLst"))
    ncs_codes = codes_of(item.get("ncsCdLst"))
    matched = [name for code, name in config.PUBLIC_JOBS_INTERN_CODES.items() if code in hire_codes]
    matched += [name for code, name in config.PUBLIC_JOBS_NCS_CODES.items() if code in ncs_codes]
    return {
        "source": "공공기관(ALIO)",
        "id": f"alio-{number}",
        "company": item.get("instNm", ""),
        "title": (item.get("recrutPbancTtl") or "").strip(),
        "career": item.get("recrutSeNm", ""),
        "location": item.get("workRgnNmLst", ""),
        "deadline": deadline,
        "deadline_text": f"{deadline:%m/%d}({WEEKDAYS[deadline.weekday()]})" if deadline else "",
        "posted_date": parse_ymd(item.get("pbancBgngYmd")),
        "job_type": item.get("hireTypeNmLst", ""),
        "from_dispatch_feed": False,
        "fixed_category": CATEGORY_INTERN,  # 코드로 이미 거른 공고라 슬랙 분류를 고정
        "matched": matched,
        "url": f"https://job.alio.go.kr/recruitview.do?idx={number}",
    }


def fetch_public_jobs():
    """조건에 맞는 공공기관 청년인턴 공고를 (공고 목록, 에러 목록)으로 돌려줌"""
    service_key = os.environ.get("DATA_GO_KR_SERVICE_KEY", "").strip()
    if not service_key:
        return [], ["공공기관 API: DATA_GO_KR_SERVICE_KEY가 없어서 건너뛰었습니다"]
    try:
        items = fetch_all_ongoing(service_key)
    except RuntimeError as error:
        return [], [str(error)]
    return [to_job(item) for item in items if is_target(item)], []


def main():
    load_env_file()
    now = datetime.now(KST)
    jobs, errors = fetch_public_jobs()
    kept, _ = filter_jobs(jobs, now)
    sections = {job["id"]: job["section"] for job in kept}

    print(f"기준 시각(KST): {now:%Y-%m-%d %H:%M} / 조건에 맞는 진행 중 공고 {len(jobs)}건\n")
    for job in sorted(jobs, key=lambda job: job["posted_date"] or now.date(), reverse=True):
        mark = f"[{sections[job['id']]}] " if job["id"] in sections else ""
        print(f"- {mark}{job['company']} | {job['title']}")
        print(f"    {job['job_type']} · {job['career']} · {job['location']} · "
              f"공고 {job['posted_date']} ~ 마감 {job['deadline_text']} · 키워드: {', '.join(job['matched'])}")
        print(f"    {job['url']}")

    deadline_count = sum(1 for job in kept if job["section"] == "오늘 마감")
    print(f"\n슬랙에 들어갈 공고: 오늘 마감 {deadline_count}건 · 새로 등록 {len(kept) - deadline_count}건")
    for error in errors:
        print("에러:", error)


if __name__ == "__main__":
    main()
