from datetime import datetime, timezone, timedelta
import re
import requests
import streamlit as st

# 페이지 기본 설정
st.set_page_config(
    page_title="학교 급식 찾아보기", page_icon="🍱", layout="centered"
)


# 한국 시간(KST) 기준 오늘 날짜 구하기
def get_today_kst():
    kst = timezone(timedelta(hours=9))
    return datetime.now(kst).date()


# 1. 학교 정보 검색 함수
def search_school(school_name):
    url = "https://open.neis.go.kr/hub/schoolInfo"
    params = {"Type": "json", "SCHUL_NM": school_name}

    try:
        response = requests.get(url, params=params, timeout=5)
        data = response.json()

        # 검색 결과 처리
        if "schoolInfo" in data:
            rows = data["schoolInfo"][1]["row"]
            return rows
        elif (
            "RESULT" in data and data["RESULT"].get("CODE") == "INFO-200"
        ):  # 데이터 없음
            return []
        else:
            return []
    except Exception:
        return []


# 검색어 보완 로직 (약어 변환 후 2차 검색)
def search_school_with_fallback(query):
    # 1차 검색
    results = search_school(query)
    if results:
        return results

    # 1차 검색 실패 시 축약어 대체 후 2차 검색
    fallback_query = query
    if "여고" in fallback_query:
        fallback_query = fallback_query.replace("여고", "여자고등학교")
    elif "고" in fallback_query and not fallback_query.endswith("고등학교"):
        # 단어 끝이나 중간의 '고'를 '고등학교'로 대체
        fallback_query = re.sub(r"고$", "고등학교", fallback_query)
        fallback_query = fallback_query.replace("고 ", "고등학교 ")

    if fallback_query != query:
        results = search_school(fallback_query)

    return results


# 2. 급식 정보 조회 함수
def get_meal_info(office_code, school_code, date_str):
    url = "https://open.neis.go.kr/hub/mealServiceDietInfo"
    params = {
        "Type": "json",
        "ATPT_OFCDC_SC_CODE": office_code,
        "SD_SCHUL_CODE": school_code,
        "MMEAL_SC_CODE": "2",  # 중식
        "MLSV_FROM_YMD": date_str,
        "MLSV_TO_YMD": date_str,
    }

    try:
        response = requests.get(url, params=params, timeout=5)
        data = response.json()

        if "mealServiceDietInfo" in data:
            row = data["mealServiceDietInfo"][1]["row"][0]
            return row
        elif "RESULT" in data and data["RESULT"].get("CODE") == "INFO-200":
            return None
        else:
            return None
    except Exception:
        return None


# --- UI 구성 ---
st.title("🍱 학교 급식 찾아보기")
st.caption("나이스 교육정보 개방 포털 API를 활용한 급식 조회 서비스입니다.")

st.markdown("---")

# 학교 검색 섹션
st.subheader("1. 학교 검색")
search_kw = st.text_input(
    "학교 이름을 입력하세요", placeholder="예: 수도여고, 서울고"
)

selected_school = None

if search_kw:
    schools = search_school_with_fallback(search_kw.strip())

    if not schools:
        st.warning(
            f"'{search_kw}'에 해당하는 학교를 찾을 수 없습니다. 정확한 이름을 입력해 주세요."
        )
    else:
        # 학교 목록을 Dropdown 옵션 형태로 가공 ("학교명 (지역)")
        options = {
            f"{s['SCHUL_NM']} ({s.get('LCTN_SC_NM', '지역 정보 없음')})": s
            for s in schools
        }

        selected_option = st.selectbox(
            "목록에서 학교를 선택해 주세요:", options=list(options.keys())
        )

        selected_school = options[selected_option]

# 급식 조회 섹션
if selected_school:
    st.markdown("---")
    st.subheader(f"2. {selected_school['SCHUL_NM']} 급식 조회")

    # 날짜 선택 (기본값: KST 기준 오늘)
    today_kst = get_today_kst()
    selected_date = st.date_input("날짜를 선택하세요", value=today_kst)

    # API용 날짜 포맷 (YYYYMMDD)
    formatted_date = selected_date.strftime("%Y%m%d")

    # 급식 정보 조회 실행
    meal = get_meal_info(
        selected_school["ATPT_OFCDC_SC_CODE"],
        selected_school["SD_SCHUL_CODE"],
        formatted_date,
    )

    st.markdown("---")

    if meal:
        st.success(
            f"📅 **{selected_date.strftime('%Y년 %m월 %d일')} 중식 메뉴**"
        )

        # HTML 태그 <br/> 제거 및 줄바꿈 처리
        raw_menu = meal.get("DDISH_NM", "")
        clean_menu = raw_menu.replace("<br/>", "\n").replace("<br>", "\n")

        # 메뉴 출력 Box
        st.info(clean_menu)

        # 칼로리 정보 출력
        cal_info = meal.get("CAL_INFO", "정보 없음")
        st.metric(label="🔥 칼로리", value=cal_info)

    else:
        st.info(
            f"📌 {selected_date.strftime('%Y년 %m월 %d일')}에는 등록된 중식 급식 정보가 없습니다. (주말, 공휴일 또는 방학)"
        )
