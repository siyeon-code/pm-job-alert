# -*- coding: utf-8 -*-
"""
수집 조건 설정 파일

조건을 바꾸고 싶으면 이 파일만 고치면 됩니다.
코드값은 사람인 API 코드표 원문에서 확인한 값입니다. (2026-09-11 확인)
"""

# =========================================================
# 시간 기준: "오늘"은 항상 한국 시간으로 계산
# =========================================================
TIMEZONE = "Asia/Seoul"

# =========================================================
# "새로 등록" 기준: 실행 시점부터 몇 시간 전까지 등록된 공고를 볼지
# (오늘 0시 기준으로 하면 9시 이후 올라온 공고가 영영 안 잡혀서 24시간 기준으로 정함)
# GitHub Actions 예약 실행은 늦게 시작될 수 있어서(공식 문서) 2시간 여유를 더함.
# 겹치는 공고는 중복 방지(sent_jobs.json)가 걸러주므로 두 번 가지 않음.
# =========================================================
NEW_POSTING_WINDOW_HOURS = 26

# =========================================================
# 사람인 API 기본값
# 문서: https://oapi.saramin.co.kr/guide/job-search
# =========================================================
SARAMIN_API_URL = "https://oapi.saramin.co.kr/job-search"
SARAMIN_PAGE_SIZE = 110  # count 최대값이 110이라 한 번에 110건씩 받음

# =========================================================
# 지역: 1차 근무지 코드 (loc_mcd)
# 코드표: https://oapi.saramin.co.kr/guide/code-table2
# =========================================================
REGION_CODES = {
    "101000": "서울전체",
    "102000": "경기전체",
}

# =========================================================
# 직무: 상위 직무 코드 (job_mid_cd)
# 코드표: https://oapi.saramin.co.kr/guide/code-table5
# =========================================================
JOB_MID_CODE_PLANNING = "16"  # 기획·전략

# =========================================================
# 고용형태: 파견직만 빼고 나머지는 모두 포함
# 코드표: https://oapi.saramin.co.kr/guide/code-table1
# API의 job_type 검색은 문서상 1~15만 받아서(기간제=16 등이 빠짐),
# 서버에서 거르지 않고 받아온 뒤 코드에서 제외합니다. (3단계)
# =========================================================
EXCLUDED_JOB_TYPE_CODES = {"6"}  # 6 = 파견직

# =========================================================
# 직무 키워드: 공고 제목에서 부분일치로 찾음 (3단계에서 사용)
# 표기가 제각각이라 띄어쓰기 버전도 함께 넣어둠
# =========================================================
CORE_KEYWORDS = [
    "PM", "PO", "프로덕트 매니저", "프로덕트 오너",
    "Product Manager", "Product Owner",
    "서비스 기획", "서비스기획", "웹기획", "앱기획", "IT기획",
]

EXTENDED_KEYWORDS = [
    "사업기획", "전략기획", "주니어 기획자",
    "서비스 운영", "프로덕트 운영", "그로스",
]

DOMAIN_KEYWORDS = [
    "데이터 기획", "CX 기획", "커머스 기획", "헬스케어 기획", "웰니스",
]

# 인턴 계열: 기획 계열 공고에 이 키워드가 있으면 슬랙 2번 섹션(인턴·계약직)으로 분류
INTERN_KEYWORDS = [
    "인턴", "인턴십", "Intern", "체험형 인턴", "채용연계형 인턴",
]

# 신입 계열: 기획 계열 공고에 이 키워드가 있으면 슬랙 1번 섹션(정규직·신입)으로 분류
ENTRY_KEYWORDS = [
    "신입", "주니어", "어시스턴트 기획자",
]

# 계약직 판단용 제목 키워드 (인크루트 RSS에는 고용형태 정보가 없어서 제목으로 판단)
CONTRACT_KEYWORDS = ["계약직", "기간제"]

# 제목에 하나라도 들어 있으면 버리는 키워드
EXCLUDE_KEYWORDS = [
    "광고기획", "마케팅기획", "MD", "공간기획", "전시기획", "영업기획", "콘텐츠기획",
]

# =========================================================
# 필터 규칙 (3단계)
# =========================================================
# 제목에 이 글자가 있으면 "기획 계열"로 봄 (인턴·계약직 섹션 판단에 사용)
PLANNING_FAMILY_WORD = "기획"

# 지역: 근무지 표기에 이 글자가 하나라도 있으면 통과
# ("전국" 공고도 받고 싶으면 목록에 "전국"을 추가)
REGION_KEYWORDS = ["서울", "경기"]

# 경력: 요구하는 최소 경력(년)이 이 값 이하이면 통과. 신입·경력무관은 0년으로 봄
MAX_CAREER_YEARS = 3

# 파견 판단용 제목 키워드 (사람인은 고용형태 코드 6으로도 판단)
DISPATCH_TITLE_KEYWORDS = ["파견"]

# 사람인 고용형태 중 2번 섹션(인턴·계약직)으로 보낼 코드
# 정규직이 아닌 형태는 모두 여기로 보냄 (코드표: https://oapi.saramin.co.kr/guide/code-table1)
INTERN_CONTRACT_JOB_TYPE_CODES = {
    "2": "계약직",
    "4": "인턴직",
    "5": "아르바이트",
    "8": "위촉직",
    "9": "프리랜서",
    "10": "계약직 (정규직 전환가능)",
    "11": "인턴직 (정규직 전환가능)",
    "12": "교육생",
    "14": "파트",
    "16": "기간제",
    "18": "전문계약직",
}

# =========================================================
# 인크루트 RSS
# 공식 RSS 안내: https://people.incruit.com/rss/rss.asp
# 사용 원칙: 공식 RSS 주소만 하루 1번 읽고, 공고 상세 페이지는 접근하지 않음
#           결과는 본인 비공개 슬랙 채널에만 보내고, 출처(인크루트)와 원문 링크를 표시
# =========================================================
USE_INCRUIT_RSS = True  # False로 바꾸면 인크루트는 슬랙 하단 링크로만 제공

INCRUIT_RSS_URL = "https://www.incruit.com/rss/job.asp"

# 읽을 피드: 기획 관련 직종 하위 분류 (피드마다 최신 20건씩 옴)
INCRUIT_FEEDS = {
    "웹기획·PM": {"ct": "1", "ty": "2", "cd": "420"},
    "서비스기획·운영": {"ct": "1", "ty": "3", "cd": "15854"},
    "웹서비스기획": {"ct": "1", "ty": "3", "cd": "16946"},
}

# 파견대행 공고 피드: 여기 나온 공고는 파견으로 보고 3단계에서 제외
# (인크루트 RSS에는 고용형태 정보가 없어서 이 피드로 대신 판단)
INCRUIT_DISPATCH_FEED = {"jobtycd": "3", "today": "y"}

# 요청할 때 밝히는 프로그램 이름 (브라우저인 척하지 않음)
USER_AGENT = "pm-job-alert/1.0 (personal RSS reader)"

# =========================================================
# 슬랙 알림 (4단계)
# =========================================================
# 메시지 하단 "직접 확인용 링크" (0단계에서 실제로 열리는지 확인한 검색 주소)
SEARCH_LINKS = [
    ("사람인 · 서비스기획", "https://www.saramin.co.kr/zf_user/search/recruit?searchType=search&searchword=%EC%84%9C%EB%B9%84%EC%8A%A4%EA%B8%B0%ED%9A%8D&loc_mcd=101000%2C102000&exp_cd=1%2C2%2C99&exp_max=3&recruitSort=reg_dt"),
    ("원티드 · PM·PO", "https://www.wanted.co.kr/wdlist/507/559?country=kr&job_sort=job.latest_order&years=0&years=3&locations=seoul.all&locations=gyeonggi.all"),
    ("원티드 · 서비스 기획자", "https://www.wanted.co.kr/wdlist/507/565?country=kr&job_sort=job.latest_order&years=0&years=3&locations=seoul.all&locations=gyeonggi.all"),
    ("인크루트 · 웹기획·PM", "https://job.incruit.com/jobdb_list/searchjob.asp?ct=1&ty=2&cd=420&rgn2=11&rgn2=18"),
    ("캐치 · 서비스기획", "https://www.catch.co.kr/NCS/RecruitSearch?search=%EC%84%9C%EB%B9%84%EC%8A%A4%EA%B8%B0%ED%9A%8D"),
    ("링커리어 · 신입", "https://linkareer.com/list/recruit?filterBy_jobTypes=NEW&filterBy_status=OPEN&orderBy_direction=DESC&orderBy_field=RECENT"),
    ("링커리어 · 인턴", "https://linkareer.com/list/intern?filterBy_activityTypeID=5&filterBy_jobTypes=INTERN&filterBy_status=OPEN&orderBy_direction=DESC&orderBy_field=RECENT"),
    ("잡플래닛 · 전체 공고", "https://www.jobplanet.co.kr/job_postings/search"),
]

# 조건에 맞는 공고가 하나도 없을 때 보내는 한 줄
NO_JOBS_MESSAGE = "오늘은 조건에 맞는 공고가 없습니다"

# 중복 방지: 보낸 공고 번호를 적어두는 파일과 기록 보관 기간(일)
SENT_JOBS_FILE = "sent_jobs.json"
SENT_JOBS_KEEP_DAYS = 60

# =========================================================
# 공공기관 채용정보 API (재정경제부, 공공데이터포털)
# 문서: https://www.data.go.kr/data/15125273/openapi.do
# 코드는 참고문서 "코드 정의서 v1.2"에서 확인
# =========================================================
USE_PUBLIC_JOBS_API = True  # False로 바꾸면 공공기관 공고는 받지 않음

PUBLIC_JOBS_API_URL = "https://apis.data.go.kr/1051000/recruitment/list"
PUBLIC_JOBS_PAGE_SIZE = 300  # 서울·경기 진행 중 공고가 200건 안팎이라 보통 1번 호출로 다 받음
PUBLIC_JOBS_MAX_PAGES = 5    # 공고가 많아져도 하루 호출이 5번을 넘지 않게 제한

# 연결이 순간적으로 안 될 때 다시 시도 (2026-09-14 GitHub Actions에서 한 번 연결 시간 초과가 있었고,
# 바로 다시 점검했을 때는 5번 모두 정상이었음)
PUBLIC_JOBS_RETRIES = 3              # 최대 시도 횟수
PUBLIC_JOBS_RETRY_WAIT_SECONDS = 5   # 다시 시도하기 전에 기다리는 시간(초)

# 근무지: 서울, 경기
PUBLIC_JOBS_REGION_CODES = {"R3010": "서울", "R3017": "경기"}

# 고용형태: 청년인턴 계열만
PUBLIC_JOBS_INTERN_CODES = {"R1050": "청년인턴", "R1060": "청년인턴(체험형)", "R1070": "청년인턴(채용형)"}

# 직무(NCS): 경영·회계·사무, 정보통신 ("사업관리"는 현장직 공고가 섞여서 뺌)
PUBLIC_JOBS_NCS_CODES = {"R600002": "경영.회계.사무", "R600020": "정보통신"}

# 채용구분: 신입, 신입+경력 (경력만 뽑는 공고는 제외)
PUBLIC_JOBS_ENTRY_CODES = {"R2010": "신입", "R2030": "신입+경력"}
