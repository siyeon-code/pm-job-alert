# -*- coding: utf-8 -*-
"""
중복 방지: 이미 슬랙으로 보낸 공고 번호를 파일에 적어두고, 다음 실행 때 빼는 기능

저장 파일 (config.SENT_JOBS_FILE, 기본 sent_jobs.json)
  {"incruit-2609110002183": "2026-09-14", ...}
  공고 id → 보낸 날짜만 저장함. 제목·회사명 같은 공고 내용은 저장하지 않음.
"""
import json
import os
from datetime import timedelta

import config

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SENT_FILE = os.path.join(BASE_DIR, config.SENT_JOBS_FILE)


def load_sent():
    """보낸 공고 기록을 읽음. 파일이 없으면 빈 기록을 돌려줌"""
    if not os.path.exists(SENT_FILE):
        return {}
    with open(SENT_FILE, encoding="utf-8") as f:
        return json.load(f)


def remove_already_sent(jobs, sent):
    """이미 보낸 공고를 빼고 나머지만 돌려줌"""
    return [job for job in jobs if job["id"] not in sent]


def save_sent(sent, jobs, today):
    """이번에 보낸 공고를 기록에 더하고, 보관 기간이 지난 기록은 지운 뒤 파일로 저장"""
    for job in jobs:
        sent[job["id"]] = today.isoformat()
    oldest = (today - timedelta(days=config.SENT_JOBS_KEEP_DAYS)).isoformat()
    kept = {job_id: day for job_id, day in sent.items() if day >= oldest}
    with open(SENT_FILE, "w", encoding="utf-8") as f:
        json.dump(kept, f, ensure_ascii=False, indent=2, sort_keys=True)
    return kept
