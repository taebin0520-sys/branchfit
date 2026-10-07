"""공공데이터 점포 CSV → v5 점포 파일 변환 로직.

- 입력 CSV의 컬럼명·ATM 구분 기준은 확인된 바가 없어서, 호출하는 쪽이 명시적으로 넘깁니다.
- 필터 순서: ① 서울 → ② ATM 제외 → ③ 기업금융센터 제외. 단계마다 행 수를 기록합니다.
- 기대 행 수와 다르면 억지로 맞추지 않고 차이만 보고합니다.
- 좌표는 만들지 않습니다(lat, lon 컬럼은 비워 둡니다).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

V5_COLUMNS = [
    "branch_id", "branch_name", "branch_type", "region_code", "region_name",
    "address", "lat", "lon", "coord_source", "coord_status",
    "name_source", "source_date",
]


@dataclass
class PrepSpec:
    name_col: str
    address_col: str
    atm_col: str
    atm_pattern: str                 # atm_col 값에 이 정규식이 들어 있으면 ATM 행
    type_col: str | None = None      # 없으면 branch_type 은 '영업점'
    exclude_name_pattern: str = "기업금융센터"
    seoul_keyword: str = "서울"
    source_date: str = "2025-12-31"
    expected_after_atm: int = 185    # 서울, 기업금융센터 포함 기준
    expected_final: int = 182


@dataclass
class PrepResult:
    table: pd.DataFrame | None
    steps: list = field(default_factory=list)       # (단계명, 행 수)
    notes: list = field(default_factory=list)
    ok: bool = False


def _district_of(address: str, region_names: list[str]) -> str | None:
    tokens = str(address).replace(",", " ").split()
    for tok in tokens:
        if tok in region_names:
            return tok
    return None


def prepare_v5(raw: pd.DataFrame, regions: pd.DataFrame, spec: PrepSpec) -> PrepResult:
    res = PrepResult(table=None)
    for col in [spec.name_col, spec.address_col, spec.atm_col]:
        if col not in raw.columns:
            res.notes.append(f"컬럼 없음: {col} (실제 컬럼: {list(raw.columns)})")
            return res

    df = raw.copy()
    res.steps.append(("원본", len(df)))

    df = df[df[spec.address_col].astype(str).str.contains(spec.seoul_keyword, na=False)]
    res.steps.append(("① 서울", len(df)))

    is_atm = df[spec.atm_col].astype(str).str.contains(spec.atm_pattern, regex=True, na=False)
    df = df[~is_atm]
    res.steps.append(("② ATM 제외", len(df)))
    if len(df) != spec.expected_after_atm:
        res.notes.append(
            f"②단계 기대 {spec.expected_after_atm}건, 실제 {len(df)}건 "
            f"(차이 {len(df) - spec.expected_after_atm:+d})"
        )

    hq = df[spec.name_col].astype(str).str.contains(spec.exclude_name_pattern, regex=True, na=False)
    res.notes.append(f"제외 대상 {int(hq.sum())}건: {df.loc[hq, spec.name_col].tolist()}")
    df = df[~hq]
    res.steps.append(("③ 기업금융센터 제외", len(df)))
    if len(df) != spec.expected_final:
        res.notes.append(
            f"③단계 기대 {spec.expected_final}건, 실제 {len(df)}건 "
            f"(차이 {len(df) - spec.expected_final:+d})"
        )

    names = regions["region_name"].tolist()
    code_of = dict(zip(regions["region_name"], regions["region_code"].astype(str)))
    district = df[spec.address_col].map(lambda a: _district_of(a, names))
    unmapped = df.loc[district.isna(), spec.name_col].tolist()
    if unmapped:
        res.notes.append(f"자치구를 찾지 못한 행 {len(unmapped)}건: {unmapped}")

    out = pd.DataFrame({
        "branch_name": df[spec.name_col].astype(str).str.strip().values,
        "branch_type": (df[spec.type_col].astype(str).values if spec.type_col else "영업점"),
        "region_name": district.values,
        "address": df[spec.address_col].astype(str).str.strip().values,
    })
    out = out.dropna(subset=["region_name"]).copy()
    out["region_code"] = out["region_name"].map(code_of)
    out = out.sort_values(["region_code", "branch_name"]).reset_index(drop=True)
    out["branch_id"] = [
        f"IBK-{code}-{n:02d}"
        for code, n in zip(out["region_code"], out.groupby("region_code").cumcount() + 1)
    ]
    out["lat"] = None
    out["lon"] = None
    out["coord_source"] = ""
    out["coord_status"] = "missing"
    out["name_source"] = "official"
    out["source_date"] = spec.source_date
    res.table = out[V5_COLUMNS]

    # 자치구별 점포 수 ↔ 지역 파일 선언값
    counted = res.table.groupby("region_code").size()
    declared = regions.set_index(regions["region_code"].astype(str))["ibk_branches"]
    diff = (counted.reindex(declared.index).fillna(0) - declared)
    diff = diff[diff != 0]
    if not diff.empty:
        res.notes.append(f"자치구별 점포 수 불일치(실제-선언): {diff.astype(int).to_dict()}")

    res.ok = (
        len(res.table) == spec.expected_final and not unmapped and diff.empty
    )
    return res
