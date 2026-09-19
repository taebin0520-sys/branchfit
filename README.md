> 📁 **포트폴리오 프로젝트입니다.**
> Wanted AI Championship 2026 해커톤 기획서(BranchFit P0)를 기반으로 개인적으로 설계·구현한 프로젝트이며, 별도 팀/해커톤 제출물이 아닙니다.
> 데모: https://branchfit-c7fewtvqdphxpfvsfzt4ws.streamlit.app/

# BranchFit P0

개별 점포 통·폐합 **검토를 지원**하는 AI 에이전트 프로토타입.
공개 외부데이터로 소속 자치구의 지역 맥락 지표를 집계하고, AI 에이전트가 근거·한계·추가 확인 필요영역을 브리핑합니다.

> **통·폐합 여부를 판정하거나 추천하지 않습니다.** 최종 판단은 담당자가 수행합니다.
> BranchFit은 IBK기업은행의 공식 서비스가 아니며, 공개 영업점 정보를 활용한 제3자 분석 프로토타입입니다.

- `dataset_version`: `2026-09-19_v4`
- 모집단: 서울 25개 자치구 / 분석 대상 IBK 영업점 182개

---

## 1. 핵심 설계 원칙

| 담당 | 하는 일 |
|---|---|
| **결정론적 코드** | 지표 계산, percentile, 상대 라벨, 경계 판정, Peer 선정, 검토 사유 선택 |
| **AI 에이전트** | 위 결과를 읽기 쉬운 브리핑으로 **재구성** |
| **인간 담당자** | 최종 의사결정 |

AI는 숫자를 계산하지 않습니다. 계산은 코드가 끝내고, AI는 그 결과를 설명만 합니다.
**틀린 숫자로 만든 근거는 실무에서 쓸 수 없기 때문**입니다.

---

## 2. 실행 방법

```bash
# 1) 가상환경
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2) 설치
pip install -r requirements.txt

# 3) 데이터 자기점검 (pandas 없이도 동작)
python scripts/selfcheck.py

# 4) 테스트
pytest -q

# 5) 화면 실행
streamlit run app.py
```

### AI 에이전트(LLM) 연결 — 선택 사항

**설정하지 않아도 모든 화면과 브리핑이 정상 동작합니다.**
LLM이 없으면 결정론적 템플릿 브리핑이 표시됩니다.

```bash
export BRANCHFIT_LLM_API_KEY="발급받은_키"
export BRANCHFIT_LLM_BASE_URL="https://api.openai.com/v1"   # 생략 가능
export BRANCHFIT_LLM_MODEL="gpt-4o-mini"                     # 생략 가능
streamlit run app.py
```

OpenAI 호환 `/chat/completions` 엔드포인트면 `BASE_URL`만 바꿔 그대로 씁니다.
API 키는 코드에 절대 넣지 않고 환경변수로만 주입합니다.

---

## 3. 파일 구조와 역할

```
branchfit/
├── app.py                      Streamlit 결과화면 (기획서 3.2 정보 우선순위 순서대로 배치)
├── branchfit/
│   ├── config.py               고정 상수 — 기획서에서 '사람이 정한 값'만 모음
│   ├── data.py                 원천 CSV 로딩 + 정합성 검증 (25행 / 182개 / 자치구별 합계)
│   ├── metrics.py              지역 맥락 지표·percentile·상대 라벨·경계 판정
│   ├── peers.py                규모 유사 Peer 자치구 2곳 선정
│   ├── review.py               notable indicator / 검토 사유 / 추가 확인 영역 선정
│   ├── contract.py             AI 입력 JSON 빌드  ← 여기부터 pandas 없음
│   ├── validator.py            AI 출력 검증 (구조 → 수치 대조 → 고유명 → 금지표현)
│   ├── briefing.py             LLM 호출 + 결정론적 템플릿 fallback
│   └── pipeline.py             위 순서를 잇는 조립부
├── data/raw/
│   ├── seoul_districts_2026-09-19_v4.csv   자치구 25행 (인구·사업체·영업점 수)
│   └── ibk_branches_2026-09-19_v4.csv      개별 점포 182행 (Point Data Layer)
├── scripts/
│   ├── make_branch_seed.py     점포 목록 CSV 생성 (자치구별 합계와 구조적으로 일치)
│   └── selfcheck.py            의존성 없는 데이터·가드레일 자기점검
└── tests/
    ├── test_metrics.py         계산식·라벨 경계·라벨 분포
    ├── test_peers.py           Peer 거리·동률 처리·결정성
    └── test_guardrails.py      contract / validator / fallback (pandas 불필요)
```

### 레이어 경계를 pandas 기준으로 나눈 이유

```
[pandas 레이어]  data → metrics → peers        숫자를 다루는 곳
        ↓ dict로 변환
[표준 라이브러리]  contract → validator → briefing   AI와 검증을 다루는 곳
```

검증기는 시스템의 **마지막 안전장치**입니다. 의존성을 최소로 두면
pandas/streamlit이 없는 환경에서도 가드레일만 따로 테스트할 수 있습니다.
(실제로 `tests/test_guardrails.py`는 pandas 없이 24건 통과)

---

## 4. 계산 로직 (기획서 6~8절)

### 주지표 / 보조지표

```
biz_per_1k  = ibk_branches / biz_count  × 1,000     ← 주지표
pop_per_10k = ibk_branches / total_pop  × 10,000    ← 보조지표
```

주지표를 사업체 기준으로 삼는 이유: 자치구별 사업체 규모 차이가 커서
영업점 **개수**를 그대로 비교하면 규모가 큰 자치구가 항상 많아 보입니다.

### Percentile과 상대 라벨

```python
Series.rank(method="min", pct=True, ascending=True) * 100
```

| percentile | 라벨 |
|---|---|
| p ≤ 30 | 상대 저밀도 |
| 30 < p < 70 | 상대 중간 |
| p ≥ 70 | 상대 고밀도 |

- `method="min"`: 동률이면 더 낮은 순위를 공유 → 정렬 순서에 따라 값이 흔들리지 않음(재현성)
- **30/70은 통계기관·금융당국 기준이 아니라 BranchFit의 UI 표현 기준**입니다
- 라벨 판정은 **반올림하지 않은 원 percentile**로 합니다

> 참고: 25개 지역의 `biz_per_1k`가 모두 서로 다르면 분포는 percentile 규칙상
> **항상 저밀도 7 / 중간 10 / 고밀도 8**이 됩니다(rank 1–7, 8–17, 18–25).
> 이 값이 달라졌다면 동률 발생 또는 데이터 행 수 변경을 뜻합니다.

### 경계 인접 / 지표 충돌

- `boundary_adjacent`: 사업체 percentile이 28–32 또는 68–72 → 위험 경고가 아니라 **중립 표시**
- `density_label_conflict`: 사업체 기준 라벨 ≠ 인구 기준 라벨 → 고정 문구로만 표시하고 **원인을 추론하지 않음**

### Peer

```
거리 = |총인구 규모 percentile 차| + |사업체 규모 percentile 차|
```

- 자기 자신·결측 제외, 거리 오름차순 2곳, 동률은 `region_code` 오름차순
- 거리값을 소수 6자리로 고정 반올림 → **부동소수점 오차로 동률 순서가 흔들리는 문제 방지**
- Peer는 밀도가 비슷한 곳이 아니라 **규모가 비슷한 비교지역**입니다. 우수/열위 지역이 아닙니다.

---

## 5. AI 가드레일 (기획서 10절)

```
구조화 입력 → LLM → 검증 ─통과→ 화면 노출
                      └실패→ 1회 재시도 ─실패→ 결정론적 템플릿 fallback
```

검증 4단계:

| 단계 | 막는 것 |
|---|---|
| 1. 구조 검증 | 필드 누락, 타입 오류, 허용되지 않은 필드 추가 |
| 2. 수치 대조 | 입력 JSON에 없는 숫자 (예: "반경 1.4km") |
| 3. 고유명 검출 | 입력에 없는 지역명·점포명 (예: "성북구", "삼성기업금융센터") |
| 4. 금지표현 | 결정·추천·예측 (예: "통·폐합해야", "추천합니다", "수익성이 낮습니다") |

**템플릿 fallback은 고정 상수 문구 + contract의 숫자로만 조립하므로 항상 검증을 통과합니다.**
→ 어떤 상황에서도 화면이 비지 않습니다. `scripts/selfcheck.py`가 182개 전 점포에 대해 이를 확인합니다.

### 한계 문구는 막지 않습니다

"수익성", "거래량" 같은 단어 자체를 금지하면
*"공개데이터로는 수익성을 알 수 없습니다"* 같은 **정당한 한계 문구까지 차단**됩니다.
그래서 단어가 아니라 **단정하는 어법**(`수익성이 낮다`, `거래량이 적다`)을 막습니다.

### 한국어 조사 처리

`부산진구와`, `인구는`처럼 한국어는 명사 뒤에 조사가 붙어서
정규식 뒤쪽 조건만으로는 지역명과 일반명사를 구분할 수 없습니다.
그래서 **허용된 고유명을 먼저 지우고, 남은 `~구` 토큰을 검사**합니다.
(`남구로영업점`에서 `남구`를 다른 지역명으로 오탐하는 문제도 같이 해결)

---

## 6. 데이터 상태 — 중요

데이터 상태가 **항목마다 다릅니다.** CSV의 `data_status` / `name_source` 컬럼에 표시되어 있습니다.

| 데이터 | 상태 | 비고 |
|---|---|---|
| 자치구 수치 (`total_pop`, `elderly_pop`, `biz_count`, `ibk_branches`) | ✅ **official** | 공식 통계 반영 완료 |
| 개별 점포명 (`branch_name`) | ⚠️ **synthetic_placeholder** | 자치구별 **개수는 공식값**, 점포명은 합성 라벨 |
| 점포 주소·좌표·운영상태 | ❌ 미수집 | 애초에 컬럼을 만들지 않음 (기획서 5.1) |

즉 **지역 맥락 지표(주지표·보조지표·percentile·라벨·Peer)는 전부 공식 데이터 기반**이고,
개별 점포는 "몇 개인지"만 공식이며 "이름이 무엇인지"는 아직 아닙니다.
기획서 14절에서 개별 점포 식별정보 QA를 별도 과제로 둔 것과 같은 경계입니다.

화면에서도 점포를 선택하면 점포명이 합성값이라는 안내가 함께 표시됩니다.

### 데이터를 교체하는 절차

1. 아래 출처에서 원본을 내려받습니다.

   | 필드 | 출처 | 기준시점 |
   |---|---|---|
   | `total_pop`, `elderly_pop` | [행정안전부 주민등록 인구통계](https://jumin.mois.go.kr/ageStatMonth.do) | 2026-07-31 |
   | `biz_count` | [KOSIS 전국사업체조사](https://kosis.kr/) | 2024-12-31 |
   | `ibk_branches`, 점포 목록 | [IBK 공식 영업점찾기](https://kiupbank.ttmap.co.kr/main.jsp) | 2026-09-19 |
   | 교차검증 | [공공데이터포털 IBK 점포명세](https://www.data.go.kr/data/15006875/fileData.do) | — |

2. `data/raw/seoul_districts_<버전>.csv`의 수치를 교체하고 `data_status`를 `official`로 바꿉니다.
3. 점포 목록은 실제 점포명으로 교체하고 `name_source`를 `official`로 바꿉니다.
   (자치구별 점포 수는 `ibk_branches`와 반드시 일치해야 합니다)
4. `python scripts/make_branch_seed.py` → 점포 목록 재생성 (자치구별 합계 자동 일치)
5. `python scripts/selfcheck.py` → 전부 PASS 확인.
6. 기준시점이 바뀌면 `config.DATASET_VERSION`을 올리고 파일명도 함께 바꿉니다.

### 데이터 버전 이력

| 버전 | 자치구 수치 | IBK 기준시점 | 비고 |
|---|---|---|---|
| `2026-09-08_v3` | placeholder(합성값) | 2026-09-08 | 파이프라인·화면·가드레일 선행 구축 |
| `2026-09-19_v4` | **official** | 2026-09-19 | 공식 통계 반영. IBK 조회 시점이 바뀌어 버전 상향 |

버전을 올린 이유는 값이 바뀌었기 때문이 아니라 **기준시점이 바뀌었기 때문**입니다.
기준시점이 달라졌는데 버전을 그대로 두면 같은 버전으로 서로 다른 결과가 나와 재현이 불가능해집니다.

v4 반영 시 실제 집계 합계가 기획서에 기록된 **182개와 정확히 일치**했습니다
(`scripts/selfcheck.py`의 `IBK 합계 182` 항목).

### 은행 내부데이터는 어떻게 가져올 것인가 (설계만, P0 구현 제외)

내부 실적데이터는 **연동하지 않습니다.** 대신 경계를 이렇게 둡니다.

- 내부데이터가 들어올 자리는 `contract.py`의 `branch` 블록 하나로 고정
- 내점고객 수·이용실적 같은 항목은 지금 **추정하지 않고**, `next_internal_data_candidates`로 "담당자가 직접 확인할 영역"으로만 표시
- 즉 P0는 내부데이터의 **빈자리를 명시**하는 방식으로 설계되어 있고, 실제 연동 시에도 지표 계산식은 바뀌지 않습니다

---

## 7. P0 Non-goal (하지 않는 것)

- 통·폐합 자동 판정 / 최종 추천 / 대상 점포 랭킹
- 은행 내부 실적·수익성 데이터 결합
- 금융위원회 공식 사전영향평가 수행 또는 대체
- 신설·폐쇄·최적입지·대체수단 추천, 금융수요 예측
- 대체점포 거리·타행 ATM 분포 (외부데이터 확장 후보 → P1)

화면의 "점포 목록 정렬"은 목록을 찾기 쉽게 하는 정렬일 뿐이며,
**통·폐합 우선순위가 아닙니다.**

---

## 8. 검증 현황

`python scripts/selfcheck.py` → **25/25 PASS**

```
자치구 행 수 25 · region_code 중복 없음 · IBK 합계 182 · 점포 행 수 182
자치구별 점포 수 == ibk_branches · 출장소 4곳 · biz_per_1k 동률 없음
상대 라벨 분포 저7/중10/고8 · Peer 각 2곳 · Peer 결정성(입력 순서 무관)
182개 전 점포 템플릿 브리핑 검증 통과
[음성] 없는 숫자/지역명/점포명 차단 · 폐쇄 권고/추천/수익성/예측 차단 · 구조 오류 차단
```

`pytest tests/test_guardrails.py` → **24 passed** (pandas 불필요)
