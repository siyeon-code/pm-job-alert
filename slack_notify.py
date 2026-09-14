# -*- coding: utf-8 -*-
"""
4단계: 필터를 통과한 공고를 슬랙 메시지로 만들고 Incoming Webhook으로 보내는 기능

슬랙 제한 (공식 문서에서 확인)
  - 메시지 1개에 블록 최대 50개
  - section 블록 글자 최대 3000자, header 블록 글자 최대 150자
  - 글자 안의 &, <, >는 &amp; &lt; &gt; 로 바꿔야 그대로 보임
"""
import time

import requests

import config
from job_filter import (
    CATEGORY_CORE,
    CATEGORY_EXTENDED,
    CATEGORY_INTERN,
    SECTION_DEADLINE,
    SECTION_NEW,
)

MAX_BLOCKS = 50
MAX_SECTION_CHARS = 3000
MAX_HEADER_CHARS = 150
WEEKDAYS = "월화수목금토일"


def escape(text):
    """슬랙이 특수하게 읽는 &, <, >를 글자 그대로 보이게 바꿈"""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def korean_date(day):
    """date(2026, 9, 14) → '9월 14일 (월)'"""
    return f"{day.month}월 {day.day}일 ({WEEKDAYS[day.weekday()]})"


def short_location(location, limit=2):
    """'서울>강남구, 서울>중구, 대전>서구' → '서울 강남구, 서울 중구 외 1곳'"""
    places = [" ".join(place.replace(">", " ").split()) for place in location.split(",") if place.strip()]
    text = ", ".join(places[:limit])
    if len(places) > limit:
        text += f" 외 {len(places) - limit}곳"
    return text


def job_line(job):
    """공고 1건을 2줄로 만듦: 제목(누르면 원문 링크) / 회사 · 경력 · 지역 · 마감 · 출처"""
    # 링크 글자 안의 |는 링크 문법(<주소|글자>)과 헷갈릴 수 있어서 /로 바꿈
    title = escape(job["title"][:150]).replace("|", "/")
    details = " · ".join([
        escape(job["company"]),
        escape(job["career"] or "경력 표기 없음"),
        escape(short_location(job["location"]) or "지역 표기 없음"),
        "마감 " + escape(job["deadline_text"] or "표기 없음"),
        job["source"],
    ])
    return f"• *<{job['url']}|{title}>*\n      {details}"


def section_block(text):
    """글자 칸(section 블록) 1개"""
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


def context_block(text):
    """작은 회색 글씨 칸(context 블록) 1개"""
    return {"type": "context", "elements": [{"type": "mrkdwn", "text": text}]}


def pack_lines(lines, limit=MAX_SECTION_CHARS):
    """여러 줄을 section 블록 글자 제한(3000자)을 넘지 않게 몇 덩어리로 묶음"""
    chunks, current = [], ""
    for line in lines:
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > limit and current:
            chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def build_job_messages(jobs, now):
    """공고 목록으로 슬랙 메시지 목록을 만듦. 블록이 50개를 넘으면 여러 메시지로 나눔"""
    if not jobs:
        return [{"text": config.NO_JOBS_MESSAGE}]

    deadline_count = sum(1 for job in jobs if job["section"] == SECTION_DEADLINE)
    new_count = sum(1 for job in jobs if job["section"] == SECTION_NEW)
    title = f"📋 채용공고 알림 · {korean_date(now.date())}"
    summary = f"⏰ 오늘 마감 {deadline_count}건 · 🆕 새로 등록 {new_count}건"
    condition = f"{'·'.join(config.REGION_KEYWORDS)} / 최소 경력 {config.MAX_CAREER_YEARS}년 이하"
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": title[:MAX_HEADER_CHARS]}},
        context_block(f"{summary} · {condition}"),
    ]

    # 섹션(오늘 마감 / 새로 등록) 안에 분류(1~3번)별로 공고를 넣음. 공고가 없는 분류는 생략
    for section_name, emoji in ((SECTION_DEADLINE, "⏰"), (SECTION_NEW, "🆕")):
        blocks.append({"type": "divider"})
        blocks.append(section_block(f"*{emoji} {section_name}*"))
        section_jobs = [job for job in jobs if job["section"] == section_name]
        if not section_jobs:
            blocks.append(section_block("_해당 공고 없음_"))
            continue
        for category in (CATEGORY_CORE, CATEGORY_INTERN, CATEGORY_EXTENDED):
            group = [job for job in section_jobs if job["category"] == category]
            if not group:
                continue
            lines = [f"*{category}* ({len(group)}건)"] + [job_line(job) for job in group]
            blocks.extend(section_block(chunk) for chunk in pack_lines(lines))

    # 하단: 사이트별 직접 확인용 링크 + 출처
    blocks.append({"type": "divider"})
    links = " · ".join(f"<{url}|{escape(name)}>" for name, url in config.SEARCH_LINKS)
    blocks.append(section_block(f"*🔎 직접 확인용 링크*\n{links}"))
    sources = sorted({job["source"] for job in jobs})
    blocks.append(context_block(f"출처: {', '.join(sources)}"))

    fallback = f"{title} — {summary}"  # 휴대폰 알림에 보이는 글
    return [
        {"text": fallback, "blocks": blocks[start:start + MAX_BLOCKS]}
        for start in range(0, len(blocks), MAX_BLOCKS)
    ]


def build_error_message(errors, now):
    """수집 중 생긴 에러를 알리는 메시지"""
    lines = "\n".join(f"• {escape(error)}" for error in errors)
    text = f"⚠️ 채용공고 알림: 수집 중 문제가 생겼어요 ({now:%Y-%m-%d %H:%M} KST)\n{lines}"
    return {"text": text[:MAX_SECTION_CHARS]}


def preview(message):
    """메시지를 터미널에서 읽기 쉬운 글자로 바꿈 (미리보기용)"""
    if "blocks" not in message:
        return message["text"]
    lines = []
    for block in message["blocks"]:
        if block["type"] == "divider":
            lines.append("─" * 40)
        elif block["type"] == "context":
            lines.append(" ".join(element["text"] for element in block["elements"]))
        else:
            lines.append(block["text"]["text"])
    return "\n".join(lines)


def send_message(message, webhook_url):
    """웹훅으로 메시지 1개를 보냄. 실패하면 RuntimeError (에러 글에 웹훅 주소는 넣지 않음)"""
    try:
        response = requests.post(webhook_url, json=message, timeout=20)
    except requests.RequestException as error:
        raise RuntimeError(f"슬랙 전송 네트워크 오류: {str(error).replace(webhook_url, '****')}") from None
    # 문서: 성공하면 HTTP 200과 본문 "ok"
    if response.status_code != 200 or response.text != "ok":
        raise RuntimeError(f"슬랙 전송 실패: HTTP {response.status_code} {response.text[:100]}")


def send_messages(messages, webhook_url):
    """메시지 여러 개를 순서대로 보냄 (메시지 사이에 1초 쉬기)"""
    for index, message in enumerate(messages):
        if index > 0:
            time.sleep(1)
        send_message(message, webhook_url)
