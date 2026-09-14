# -*- coding: utf-8 -*-
"""
전체 실행: 공고 모으기 → 거르기 → 이미 보낸 공고 빼기 → 슬랙 보내기 → 보낸 기록 저장

실행 방법
  python3 main.py          # 슬랙으로 보내지 않고 메시지 미리보기만
  python3 main.py --send   # 실제로 슬랙에 보내고, 보낸 공고를 sent_jobs.json에 기록
"""
import os
import sys
import traceback
from datetime import datetime

import config
import sent_jobs
import slack_notify
from incruit_rss import fetch_incruit_jobs
from job_filter import KST, filter_jobs
from saramin_api import load_env_file


def collect_jobs():
    """모든 출처에서 공고를 모아 (공고 목록, 에러 목록)을 돌려줌"""
    jobs, errors = [], []
    if config.USE_INCRUIT_RSS:
        incruit_jobs, incruit_errors = fetch_incruit_jobs()
        jobs += incruit_jobs
        errors += incruit_errors
    # 사람인은 access-key를 받아 1·2단계를 마친 뒤 여기에 추가
    return jobs, errors


def main():
    send = "--send" in sys.argv
    load_env_file()
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if send and not webhook_url:
        print("SLACK_WEBHOOK_URL이 없어서 보낼 수 없습니다. .env 또는 GitHub Secrets를 확인하세요.")
        sys.exit(1)

    now = datetime.now(KST)
    errors, messages, new_jobs, sent = [], [], [], {}
    try:
        jobs, errors = collect_jobs()
        kept, _ = filter_jobs(jobs, now)
        sent = sent_jobs.load_sent()
        new_jobs = sent_jobs.remove_already_sent(kept, sent)
        messages = slack_notify.build_job_messages(new_jobs, now)
        print(f"모은 공고 {len(jobs)}건 → 조건 통과 {len(kept)}건 → 이미 보낸 공고 빼고 {len(new_jobs)}건")
    except Exception:
        # 예상 못 한 오류도 슬랙으로 알림 (비밀값은 각 모듈에서 가려서 에러 글에 들어가지 않음)
        errors.append("실행 중 예상 못 한 오류\n" + traceback.format_exc(limit=3))

    # 수집 에러가 있으면 에러 알림 메시지를 따로 붙임
    if errors:
        messages.append(slack_notify.build_error_message(errors, now))

    if not send:
        print("\n[미리보기] --send 없이 실행해서 슬랙으로 보내지 않았습니다.")
        for number, message in enumerate(messages, 1):
            print(f"\n--- 메시지 {number} ---")
            print(slack_notify.preview(message))
        return

    slack_notify.send_messages(messages, webhook_url)
    if new_jobs:
        sent_jobs.save_sent(sent, new_jobs, now.date())  # 보내기에 성공한 뒤에만 기록
    print(f"슬랙으로 메시지 {len(messages)}개를 보냈고, 공고 {len(new_jobs)}건을 보낸 기록에 저장했습니다.")
    if errors:
        sys.exit(1)  # 에러가 있었으면 GitHub Actions에서도 실패로 표시되게 함


if __name__ == "__main__":
    main()
