"""원천 데이터 로딩 + 정합성 검증.

여기서 데이터를 '읽기만' 하지 않고 곧바로 검증까지 하는 이유:
기획서 14절 QA 항목(25행 / region_code 중복 없음 / IBK 합계 182 /
자치구별 점포 수 일치)을 코드로 강제해 두면,
데이터를 실제 공식 자료로 교체할 때 조용히 깨지는 일을 막을 수 있습니다.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import config

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

REGION_FILE = RAW_DIR / f"seoul_districts_{config.DATASET_VERSION}.csv"
BRANCH_FILE = RAW_DIR / f"ibk_branches_{config.DATASET_VERSION}.csv"

REGION_COLUMNS = [
    "region_code",
    "region_name",
    "total_pop",
    "elderly_pop",
    "biz_count",
    "ibk_branches",
]
BRANCH_COLUMNS = [
    "branch_id",
    "branch_name",
    "branch_type",
    "region_code",
    "region_name",
]


class DataIntegrityError(Exception):
    """데이터 정합성 검증 실패."""


def load_regions() -> pd.DataFrame:
    """서울 25개 자치구 지역 데이터를 읽습니다."""
    # region_code는 '11110'처럼 앞자리 0이 없지만, 숫자로 읽으면
    # 다른 지역으로 확장할 때 앞자리 0이 사라질 수 있어 문자열로 고정합니다.
    df = pd.read_csv(REGION_FILE, dtype={"region_code": str})
    _require_columns(df, REGION_COLUMNS, REGION_FILE.name)
    _validate_regions(df)
    return df


def load_branches() -> pd.DataFrame:
    """개별 IBK 점포 데이터를 읽습니다."""
    df = pd.read_csv(BRANCH_FILE, dtype={"region_code": str})
    _require_columns(df, BRANCH_COLUMNS, BRANCH_FILE.name)
    return df


def load_all() -> tuple[pd.DataFrame, pd.DataFrame]:
    """지역 + 점포를 함께 읽고, 두 파일 사이의 정합성까지 검증합니다."""
    regions = load_regions()
    branches = load_branches()
    _validate_cross(regions, branches)
    return regions, branches


# ---------------------------------------------------------------------------
# 검증
# ---------------------------------------------------------------------------

def _require_columns(df: pd.DataFrame, columns: list[str], filename: str) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise DataIntegrityError(f"{filename}: 필수 컬럼 누락 {missing}")


def _validate_regions(df: pd.DataFrame) -> None:
    if len(df) != config.EXPECTED_REGION_COUNT:
        raise DataIntegrityError(
            f"자치구 행 수가 {config.EXPECTED_REGION_COUNT}가 아닙니다: {len(df)}"
        )

    dup = df.loc[df["region_code"].duplicated(), "region_code"].tolist()
    if dup:
        raise DataIntegrityError(f"region_code 중복: {dup}")

    total = int(df["ibk_branches"].sum())
    if total != config.EXPECTED_BRANCH_TOTAL:
        raise DataIntegrityError(
            f"IBK 영업점 합계가 {config.EXPECTED_BRANCH_TOTAL}가 아닙니다: {total}"
        )

    # 0으로 나누기 방지: 분모가 되는 컬럼은 반드시 양수
    for col in ("total_pop", "biz_count"):
        bad = df.loc[df[col] <= 0, "region_name"].tolist()
        if bad:
            raise DataIntegrityError(f"{col}이 0 이하인 자치구: {bad}")

    # 65세 이상 인구가 총인구를 넘으면 데이터 오류
    bad = df.loc[df["elderly_pop"] > df["total_pop"], "region_name"].tolist()
    if bad:
        raise DataIntegrityError(f"elderly_pop > total_pop 인 자치구: {bad}")


def _validate_cross(regions: pd.DataFrame, branches: pd.DataFrame) -> None:
    if len(branches) != config.EXPECTED_BRANCH_TOTAL:
        raise DataIntegrityError(
            f"점포 행 수가 {config.EXPECTED_BRANCH_TOTAL}가 아닙니다: {len(branches)}"
        )

    dup = branches.loc[branches["branch_id"].duplicated(), "branch_id"].tolist()
    if dup:
        raise DataIntegrityError(f"branch_id 중복: {dup}")

    unknown = set(branches["region_code"]) - set(regions["region_code"])
    if unknown:
        raise DataIntegrityError(f"지역 데이터에 없는 region_code: {sorted(unknown)}")

    # 자치구별 점포 수 == 지역 데이터의 ibk_branches
    counted = branches.groupby("region_code").size()
    declared = regions.set_index("region_code")["ibk_branches"]
    diff = (counted - declared).dropna()
    mismatch = diff[diff != 0]
    if not mismatch.empty:
        raise DataIntegrityError(
            f"자치구별 점포 수 불일치(실제-선언): {mismatch.to_dict()}"
        )
