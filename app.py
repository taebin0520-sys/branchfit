"""BranchFit P0 — Streamlit 결과화면 (기획서 3.2 / 12절).

화면 정보 우선순위를 기획서 3.2 순서 그대로 배치했습니다.
    점포 기본정보 → 주지표 → 보조지표 → 자치구 프로필/Peer
    → AI 브리핑 → 추가 확인 필요영역 → 출처·기준시점·한계

실행:
    streamlit run app.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from branchfit import briefing as briefing_mod
from branchfit import config, peers, pipeline

st.set_page_config(page_title="BranchFit P0", page_icon="🏦", layout="wide")

#: 경계 인접 등 중립 배지 스타일.
#: 기획서 12절: 경고색·경고 아이콘을 쓰지 않고 회색 계열 중립 텍스트로 표시.
NEUTRAL_BADGE = (
    '<span style="background:#f1f3f5;color:#495057;padding:2px 8px;'
    'border-radius:10px;font-size:0.82rem;">{text}</span>'
)


@st.cache_data(show_spinner=False)
def load_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    """CSV 로딩 + 지표 계산. 결정론적이므로 캐시해도 안전합니다."""
    return pipeline.build_tables()


def neutral_badges(region: pd.Series) -> None:
    badges = []
    if region["density_label_conflict"]:
        badges.append("지표 충돌")
    if region["boundary_adjacent"]:
        badges.append("경계 인접")
    if badges:
        st.markdown(
            " ".join(NEUTRAL_BADGE.format(text=b) for b in badges),
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# 데이터 로딩
# ---------------------------------------------------------------------------
try:
    region_table, branch_table = load_tables()
except Exception as exc:  # noqa: BLE001 - 화면에 원인을 그대로 보여주는 것이 목적
    st.error(f"데이터 정합성 검증 실패: {exc}")
    st.stop()


# ---------------------------------------------------------------------------
# 사이드바 — (1) 자치구 선택 → (2) 점포 선택
# ---------------------------------------------------------------------------
st.sidebar.title("BranchFit")
st.sidebar.caption(f"dataset_version {config.DATASET_VERSION}")

region_names = region_table["region_name"].tolist()
selected_region_name = st.sidebar.selectbox("1) 자치구 선택", region_names)
region = region_table.loc[
    region_table["region_name"] == selected_region_name
].iloc[0]

region_branches = branch_table.loc[
    branch_table["region_code"] == region["region_code"]
].copy()

sort_option = st.sidebar.radio(
    "점포 목록 정렬",
    ["점포명 순", "점포 유형 순"],
    help="목록을 찾기 쉽게 하는 정렬입니다. 통·폐합 우선순위가 아닙니다.",
)
if sort_option == "점포명 순":
    region_branches = region_branches.sort_values("branch_name")
else:
    region_branches = region_branches.sort_values(["branch_type", "branch_name"])

selected_branch_name = st.sidebar.selectbox(
    "2) 점포 선택", region_branches["branch_name"].tolist()
)
branch = region_branches.loc[
    region_branches["branch_name"] == selected_branch_name
].iloc[0]

st.sidebar.markdown("---")
use_llm = st.sidebar.checkbox(
    "AI 에이전트(LLM) 호출",
    value=briefing_mod.llm_configured(),
    disabled=not briefing_mod.llm_configured(),
    help=(
        f"{config.ENV_API_KEY} 환경변수가 설정되어야 활성화됩니다. "
        "미설정 시 결정론적 템플릿 브리핑이 표시됩니다."
    ),
)
st.sidebar.caption(
    "LLM 미설정 상태에서도 모든 지표와 브리핑이 정상 표시됩니다."
)


# ---------------------------------------------------------------------------
# 본문
# ---------------------------------------------------------------------------
tab_review, tab_regions, tab_sources = st.tabs(
    ["점포 검토", "자치구 지표 전체", "데이터 · 출처 · 한계"]
)


with tab_review:
    st.title(f"{branch['branch_name']}")
    st.caption(
        f"{region['region_name']} · {branch['branch_type']} · "
        f"branch_id {branch['branch_id']}"
    )
    st.markdown(
        "이 화면은 개별 점포 통·폐합 **검토를 지원**합니다. "
        "통·폐합 여부를 판정하거나 추천하지 않으며, 최종 판단은 담당자가 수행합니다."
    )

    # --- (3) 점포 기본 정보 -------------------------------------------
    st.subheader("1. 점포 기본 정보")
    basic = st.columns(4)
    basic[0].metric("점포명", branch["branch_name"])
    basic[1].metric("점포 유형", branch["branch_type"])
    basic[2].metric("소속 자치구", region["region_name"])
    basic[3].metric("region_code", region["region_code"])
    if branch.get("name_source") == "synthetic_placeholder":
        st.caption(
            "점포명은 현재 합성(placeholder) 값입니다. 주소·좌표·운영상태는 "
            "공식 데이터 검증 전이므로 화면에 표시하지 않습니다(기획서 5.1)."
        )

    # --- (4) 지역 맥락 지표 --------------------------------------------
    st.subheader("2. 지역 맥락 지표")
    st.caption(
        "아래 지표는 소속 **자치구 단위**로 계산됩니다. 같은 자치구의 점포는 "
        "동일한 값으로 표시되며, 개별 점포의 성과·수요 차이를 의미하지 않습니다."
    )

    main_col, sub_col = st.columns(2)
    with main_col:
        st.markdown("**주지표 — 사업체 1천 개당 IBK 영업점 수**")
        st.metric(
            label=f"biz_per_1k ({region['biz_density_label']})",
            value=f"{region['biz_per_1k']:.{config.ROUND_DENSITY}f}",
            delta=f"percentile {region['biz_percentile']:.{config.ROUND_PERCENTILE}f}",
            delta_color="off",  # 증감이 아니라 위치 표시이므로 색을 쓰지 않음
        )
        st.caption(config.FIXED_PHRASES[region["biz_density_label"]])
        st.caption(config.METRIC_GUARDRAILS["biz_count"])

    with sub_col:
        st.markdown("**보조지표 — 인구 1만 명당 IBK 영업점 수**")
        st.metric(
            label=f"pop_per_10k ({region['pop_density_label']})",
            value=f"{region['pop_per_10k']:.{config.ROUND_DENSITY}f}",
            delta=f"percentile {region['pop_percentile']:.{config.ROUND_PERCENTILE}f}",
            delta_color="off",
        )
        st.caption(config.METRIC_GUARDRAILS["total_pop"])
        st.caption(config.METRIC_GUARDRAILS["ibk_branches"])

    neutral_badges(region)
    if region["density_label_conflict"]:
        st.caption(config.FIXED_PHRASES["density_label_conflict"])
    if region["boundary_adjacent"]:
        st.caption(config.FIXED_PHRASES["boundary_adjacent"])
    st.caption(
        f"상대 라벨 구간 기준: p≤{config.LOW_PERCENTILE:.0f} 저밀도 / "
        f"{config.LOW_PERCENTILE:.0f}<p<{config.HIGH_PERCENTILE:.0f} 중간 / "
        f"p≥{config.HIGH_PERCENTILE:.0f} 고밀도 — "
        f"공식 통계기준이 아닌 BranchFit의 UI 표현 기준입니다."
    )

    # --- 자치구 프로필 -------------------------------------------------
    st.subheader("3. 소속 자치구 프로필")
    profile = st.columns(5)
    profile[0].metric("총인구", f"{int(region['total_pop']):,}")
    profile[1].metric("65세 이상 인구", f"{int(region['elderly_pop']):,}")
    profile[2].metric(
        "고령인구 비율", f"{region['elderly_ratio']:.{config.ROUND_RATIO}f}%"
    )
    profile[3].metric("사업체 수", f"{int(region['biz_count']):,}")
    profile[4].metric("자치구 내 IBK 영업점", f"{int(region['ibk_branches'])}")
    st.caption(config.METRIC_GUARDRAILS["elderly_pop"])

    # --- Peer ----------------------------------------------------------
    st.subheader("4. 규모 유사 Peer 자치구")
    peer_rows = peers.find_peers(region_table, region["region_code"])
    peer_view = peers.peers_for_display(peer_rows).rename(
        columns={
            "region_name": "자치구",
            "biz_per_1k": "사업체 1천 개당 IBK 영업점 수",
            "biz_percentile": "사업체 기준 percentile",
        }
    )
    st.dataframe(peer_view, hide_index=True, width="stretch")
    st.caption(
        "Peer는 총인구·사업체 **규모**가 유사한 비교지역입니다. "
        "추천지역·우수지역·열위지역이 아니며, 통·폐합 우열 판단에 쓸 수 없습니다."
    )

    # --- (5) AI 브리핑 -------------------------------------------------
    st.subheader("5. AI 에이전트 브리핑")
    caller = briefing_mod.call_llm if use_llm else None
    with st.spinner("브리핑 생성 중..."):
        contract, outcome = pipeline.build_briefing_for_branch(
            region_table, branch_table, branch["branch_id"], llm_caller=caller
        )
    st.markdown(
        NEUTRAL_BADGE.format(text=briefing_mod.MODE_LABELS[outcome["mode"]]),
        unsafe_allow_html=True,
    )
    st.markdown(briefing_mod.render_markdown(outcome["briefing"]))

    with st.expander("브리핑 생성·검증 로그"):
        st.write(
            "검증 항목: 구조(JSON) → 수치 대조 → 입력 외 고유명 검출 → 금지표현"
        )
        if outcome["attempts"]:
            for attempt in outcome["attempts"]:
                st.write(f"시도 {attempt['attempt']}: ", attempt["errors"] or "통과")
        else:
            st.write("LLM 호출 없음 (결정론적 템플릿 사용)")

    with st.expander("AI 입력 데이터 계약 (JSON)"):
        st.caption(
            "AI는 이 JSON 안의 값만 설명할 수 있습니다. "
            "여기에 없는 숫자·지역명·점포명이 등장하면 검증에서 탈락합니다."
        )
        st.json(contract)

    # --- (6) 추가 확인 필요영역 ----------------------------------------
    st.subheader("6. 외부데이터로 확인할 수 없는 추가 확인 필요영역")
    st.caption(
        "아래 항목은 BranchFit이 추정하거나 연동하지 않습니다. "
        "실제 점포전략 의사결정 전에 담당자가 직접 확인해야 하는 영역입니다."
    )
    for item in contract["next_internal_data_candidates"]:
        st.markdown(f"- {item['text']}  `{item['id']}`")

    st.info(
        "BranchFit은 금융위원회의 공식 사전영향평가를 수행하거나 대체하지 않으며, "
        "규제 충족 여부 또는 점포 폐쇄 여부를 판단하지 않습니다."
    )


with tab_regions:
    st.subheader("서울 25개 자치구 지역 맥락 지표")
    st.caption(
        "정렬·비교 편의를 위한 전체 표입니다. 자치구 간 우열이나 "
        "통·폐합 우선순위를 뜻하지 않습니다."
    )
    columns = [
        "region_code",
        "region_name",
        "total_pop",
        "elderly_pop",
        "biz_count",
        "ibk_branches",
        "biz_per_1k",
        "biz_percentile",
        "biz_density_label",
        "pop_per_10k",
        "pop_percentile",
        "pop_density_label",
        "boundary_adjacent",
        "density_label_conflict",
    ]
    st.dataframe(
        region_table[columns].round(
            {
                "biz_per_1k": config.ROUND_DENSITY,
                "pop_per_10k": config.ROUND_DENSITY,
                "biz_percentile": config.ROUND_PERCENTILE,
                "pop_percentile": config.ROUND_PERCENTILE,
            }
        ),
        hide_index=True,
        width="stretch",
    )

    from branchfit import metrics as metrics_mod

    st.write("상대 라벨 분포:", metrics_mod.label_distribution(region_table))
    st.caption(
        "25개 지역의 biz_per_1k가 서로 다르면 percentile 규칙상 분포는 항상 "
        "저밀도 7 / 중간 10 / 고밀도 8이 됩니다. 값이 달라지면 동률 발생 또는 "
        "데이터 행 수 변경을 의미합니다."
    )


with tab_sources:
    st.subheader("데이터 출처 · 기준시점")
    evidence_rows = [
        {
            "evidence_id": key,
            "필드": value["field"],
            "출처": value["source"],
            "기준시점": value["reference_date"] or "-",
            "역할": value["role"],
            "URL": value["url"] or "-",
        }
        for key, value in config.EVIDENCE.items()
    ]
    st.dataframe(pd.DataFrame(evidence_rows), hide_index=True, width="stretch")

    st.subheader("한계 (limitations)")
    for item in config.LIMITATIONS:
        st.markdown(f"- {item}")

    st.subheader("버전")
    st.write(
        {
            "dataset_version": config.DATASET_VERSION,
            "schema_version": config.SCHEMA_VERSION,
            "분석 대상 IBK 영업점 수": config.EXPECTED_BRANCH_TOTAL,
            "모집단": config.POPULATION_LABEL,
        }
    )
    st.caption(
        "BranchFit은 IBK기업은행의 공식 서비스가 아니며, 공개된 영업점 정보를 "
        "활용한 해커톤용 제3자 분석 프로토타입입니다."
    )
