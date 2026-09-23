import calendar
from datetime import datetime, timedelta, timezone
from collections import Counter
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

        if "schoolInfo" in data:
            rows = data["schoolInfo"][1]["row"]
            return rows
        return []
    except Exception:
        return []


# 검색어 보완 로직 (약어 변환 후 2차 검색)
def search_school_with_fallback(query):
    results = search_school(query)
    if results:
        return results

    fallback_query = query
    if "여고" in fallback_query:
        fallback_query = fallback_query.replace("여고", "여자고등학교")
    elif "고" in fallback_query and not fallback_query.endswith("고등학교"):
        fallback_query = re.sub(r"고$", "고등학교", fallback_query)
        fallback_query = fallback_query.replace("고 ", "고등학교 ")

    if fallback_query != query:
        results = search_school(fallback_query)

    return results


# 2. 특정 날짜 급식 정보 조회 함수
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
            return data["mealServiceDietInfo"][1]["row"][0]
        return None
    except Exception:
        return None


# 3. 메뉴 문자열 정제 (알레르기 번호 및 원산지/특수문자 제거)
def clean_dish_name(dish_name):
    # 괄호 안의 알레르기 번호 (예: .1.2.5. 또는 (1.2.5)) 및 특수문자 제거
    cleaned = re.sub(r"[\d\.\(\)]+", "", dish_name)
    return cleaned.strip()


# 4. 한 달간 급식 메뉴 통계 집계 함수 (인증키 제약 극복을 위해 하루씩 호출)
def get_monthly_menu_stats(office_code, school_code, year, month):
    _, last_day = calendar.monthrange(year, month)
    counter = Counter()
    total_days_with_meal = 0

    # 진행 상태 표시 바
    progress_bar = st.progress(0, text="한 달 급식 데이터를 수집하고 있습니다...")

    for day in range(1, last_day + 1):
        date_str = f"{year}{month:02d}{day:02d}"
        meal = get_meal_info(office_code, school_code, date_str)

        if meal and "DDISH_NM" in meal:
            total_days_with_meal += 1
            # <br/> 또는 <br>로 분리
            dishes = re.split(r"<br\s*/?>", meal["DDISH_NM"])
            for dish in dishes:
                name = clean_dish_name(dish)
                if name:  # 빈 문자열 제외
                    counter[name] += 1

        # 진행 바 업데이트
        progress_bar.progress(day / last_day)

    progress_bar.empty()  # 작업 완료 후 진행 바 제거
    return counter, total_days_with_meal


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

    # 탭 구성: 일별 급식 / 월별 통계
    tab1, tab2 = st.tabs(["📅 일별 급식 보기", "📊 월별 자주 나온 메뉴"])

    # --- 탭 1: 일별 급식 보기 ---
    with tab1:
        today_kst = get_today_kst()
        selected_date = st.date_input("날짜를 선택하세요", value=today_kst)

        formatted_date = selected_date.strftime("%Y%m%d")
        meal = get_meal_info(
            selected_school["ATPT_OFCDC_SC_CODE"],
            selected_school["SD_SCHUL_CODE"],
            formatted_date,
        )

        if meal:
            st.success(
                f"📅 **{selected_date.strftime('%Y년 %m월 %d일')} 중식 메뉴**"
            )

            raw_menu = meal.get("DDISH_NM", "")
            clean_menu = raw_menu.replace("<br/>", "\n").replace("<br>", "\n")

            st.info(clean_menu)

            cal_info = meal.get("CAL_INFO", "정보 없음")
            st.metric(label="🔥 칼로리", value=cal_info)
        else:
            st.info(
                f"📌 {selected_date.strftime('%Y년 %m월 %d일')}에는 등록된 중식 급식 정보가 없습니다. (주말, 공휴일 또는 방학)"
            )

    # --- 탭 2: 월별 자주 나온 메뉴 통계 ---
    with tab2:
        col1, col2 = st.columns(2)
        with col1:
            selected_year = st.number_input(
                "연도", min_value=2020, max_value=2030, value=today_kst.year
            )
        with col2:
            selected_month = st.selectbox(
                "월", list(range(1, 13)), index=today_kst.month - 1
            )

        if st.button("월간 메뉴 통계 불러오기"):
            stats, days_count = get_monthly_menu_stats(
                selected_school["ATPT_OFCDC_SC_CODE"],
                selected_school["SD_SCHUL_CODE"],
                selected_year,
                selected_month,
            )

            if days_count == 0:
                st.warning(
                    f"{selected_year}년 {selected_month}월에는 등록된 급식 데이터가 없습니다."
                )
            else:
                st.success(
                    f"총 **{days_count}일**간의 급식 데이터 분석 결과입니다."
                )

                # 상위 10개 메뉴 추출
                top_menus = stats.most_common(10)

                st.markdown("### 🏆 가장 많이 나온 메뉴 TOP 10")
                for rank, (menu, count) in enumerate(top_menus, 1):
                    st.write(f"**{rank}위.** {menu} — `{count}회` 제공")
