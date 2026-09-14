# -*- coding: utf-8 -*-
"""
1단계: 사람인 API 호출 URL 확인용 스크립트

하는 일
  1) 조건별로 API 호출 URL을 만들어 화면에 보여줌 (키는 ****로 가림)
  2) 키가 있으면 조건마다 1번씩 호출해서 "총 몇 건인지(total)"만 확인
     - count=1로 보내서 공고는 1건씩만 받음 (하루 제한 아끼기)

실행 방법
  python3 saramin_api.py
"""
import math
import os
import sys
from datetime import datetime, timedelta
from urllib.parse import unquote
from zoneinfo import ZoneInfo

import requests

import config

KST = ZoneInfo(config.TIMEZONE)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_env_file():
    """프로젝트 폴더의 .env 파일을 읽어 환경변수로 등록 (이미 설정된 값은 그대로 둠)"""
    path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # 빈 줄, 주석(#), =이 없는 줄은 건너뜀
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


def to_timestamp(dt):
    """datetime을 Unix timestamp(초)로 바꿈. 시간대 헷갈릴 일이 없는 형식"""
    return int(dt.timestamp())


def build_params(access_key, conditions, count=config.SARAMIN_PAGE_SIZE):
    """사람인 API에 보낼 파라미터를 만듦 (모든 호출에 공통인 조건 + 이번 호출만의 조건)"""
    params = {
        "access-key": access_key,
        "loc_mcd": ",".join(config.REGION_CODES),  # 서울전체, 경기전체
        "fields": "posting-date,expiration-date",  # 게시일·마감일을 날짜 형식으로도 받기
        "count": count,
    }
    params.update(conditions)
    return params


def masked_url(params):
    """화면에 보여줄 URL. access-key는 ****로 가려서 키가 노출되지 않게 함"""
    safe_params = dict(params)
    safe_params["access-key"] = "****"
    url = requests.Request("GET", config.SARAMIN_API_URL, params=safe_params).prepare().url
    return unquote(url)  # %2C 같은 인코딩을 사람이 읽기 쉽게 풀어서 표시


def call_api(params):
    """API를 1번 호출해서 JSON(dict)을 돌려줌. 실패하면 RuntimeError를 냄"""
    access_key = params.get("access-key", "")
    try:
        response = requests.get(
            config.SARAMIN_API_URL,
            params=params,
            headers={"Accept": "application/json"},  # JSON으로 받기 (문서: Accept 헤더)
            timeout=20,
        )
    except requests.RequestException as error:
        # 네트워크 에러 메시지에는 키가 들어간 URL이 섞일 수 있어서 키를 가림
        message = str(error)
        if access_key:
            message = message.replace(access_key, "****")
        raise RuntimeError(f"네트워크 오류: {message}") from None

    try:
        data = response.json()
    except ValueError:
        raise RuntimeError(f"JSON이 아닌 응답 (HTTP {response.status_code}): {response.text[:200]}") from None

    # 정상 응답에는 "jobs"가 있고, 에러 응답은 {"code": 2, "message": "..."} 모양 (직접 호출해서 확인함)
    if "jobs" not in data:
        raise RuntimeError(f"사람인 API 에러 code={data.get('code')} message={data.get('message')}")
    return data


def make_checks(now):
    """확인할 조건 목록: (이름, 이번 호출에만 붙일 파라미터)"""
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_9am = today_start.replace(hour=9)
    last_24h = {
        "published_min": to_timestamp(now - timedelta(hours=config.NEW_POSTING_WINDOW_HOURS)),
        "published_max": to_timestamp(now),
    }
    planning = config.JOB_MID_CODE_PLANNING
    return [
        ("① 오늘 마감", {"deadline": "today"}),
        ("② 오늘 등록 (하루 전체)", {"published": now.strftime("%Y-%m-%d")}),
        ("③ 오늘 0시~9시 등록 (9시에 실행하면 보이는 범위)",
         {"published_min": to_timestamp(today_start), "published_max": to_timestamp(today_9am)}),
        ("④ 최근 24시간 등록", last_24h),
        ("⑤ ① + 기획·전략 직무만", {"deadline": "today", "job_mid_cd": planning}),
        ("⑥ ④ + 기획·전략 직무만", dict(last_24h, job_mid_cd=planning)),
        ("⑦ ④ + 키워드 '서비스기획'", dict(last_24h, keywords="서비스기획")),
        ("⑧ ④ + 키워드 '웹기획'", dict(last_24h, keywords="웹기획")),
        ("⑨ ④ + 키워드 '서비스기획,웹기획'", dict(last_24h, keywords="서비스기획,웹기획")),
    ]


def main():
    load_env_file()
    access_key = os.environ.get("SARAMIN_ACCESS_KEY", "").strip()
    now = datetime.now(KST)
    print(f"기준 시각(KST): {now:%Y-%m-%d %H:%M}\n")

    checks = make_checks(now)

    # 키가 없으면 URL만 보여주고 끝냄
    if not access_key:
        for name, conditions in checks:
            print(name)
            print("   ", masked_url(build_params("", conditions, count=1)))
        print("\nSARAMIN_ACCESS_KEY가 없어서 실제 호출은 하지 않았습니다.")
        print(".env.example을 복사해 .env를 만들고 키를 넣은 뒤 다시 실행하세요.")
        sys.exit(1)

    # 조건마다 1번씩 호출해서 총 건수만 확인
    totals = []
    for name, conditions in checks:
        params = build_params(access_key, conditions, count=1)  # 확인용이라 1건만 받음
        print(name)
        print("    URL:", masked_url(params))
        try:
            total = int(call_api(params)["jobs"]["total"])
        except RuntimeError as error:
            print("    실패:", error)
            totals.append(None)
            continue
        totals.append(total)
        pages = math.ceil(total / config.SARAMIN_PAGE_SIZE)
        print(f"    총 {total:,}건 (전부 받으려면 {pages}번 호출)")

    # 키워드 여러 개를 넣었을 때 OR인지 AND인지 판단 (⑦, ⑧, ⑨ 비교)
    single_a, single_b, both = totals[6], totals[7], totals[8]
    print("\n[키워드 여러 개 동작 확인]")
    if None in (single_a, single_b, both):
        print("    호출 실패가 있어서 판단하지 못했습니다.")
    elif single_a == single_b == both:
        print("    세 결과가 같아서 판단할 수 없습니다.")
    elif both >= max(single_a, single_b):
        print("    OR로 동작 (키워드 중 하나라도 있으면 검색됨)")
    elif both <= min(single_a, single_b):
        print("    AND로 동작 (키워드가 모두 있어야 검색됨)")
    else:
        print("    OR/AND로 설명되지 않는 결과입니다. 숫자를 직접 확인해 주세요.")

    # 실패한 호출도 하루 제한에 포함될 수 있어서, 보낸 횟수 전체를 셈
    print(f"\n이번 확인에 보낸 호출: {len(totals)}번 (하루 제한 500)")


if __name__ == "__main__":
    main()
