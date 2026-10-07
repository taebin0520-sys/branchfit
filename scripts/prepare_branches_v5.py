"""공공데이터포털 15006875 CSV → data/raw/ibk_branches_<버전>.csv (v5) 변환.

사용 순서
1) CSV를 data/raw/ 에 직접 넣는다. (이 스크립트는 내려받지 않는다.)
2) 컬럼 확인:
     python scripts/prepare_branches_v5.py --csv data/raw/<파일>.csv --list-columns
3) ATM 구분 기준을 정해 시험 실행(파일 저장 안 함):
     python scripts/prepare_branches_v5.py --csv ... --name-col 점포명 --address-col 주소 \
         --atm-col 구분 --atm-pattern "ATM|현금자동" --dry-run
4) 단계별 행 수가 맞으면 --dry-run 을 빼고 실행한다.

행 수가 기대와 다르면 파일을 만들지 않고 차이만 출력한다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from branchfit import config  # noqa: E402
from branchfit.branch_prep import PrepSpec, prepare_v5  # noqa: E402

OUTPUT_VERSION = "2025-12-31_v5"


def read_csv_any(path: Path) -> pd.DataFrame:
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            return pd.read_csv(path, encoding=enc, dtype=str)
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"인코딩을 읽을 수 없습니다: {path}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, type=Path)
    ap.add_argument("--list-columns", action="store_true")
    ap.add_argument("--name-col")
    ap.add_argument("--address-col")
    ap.add_argument("--atm-col")
    ap.add_argument("--atm-pattern")
    ap.add_argument("--type-col")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    raw = read_csv_any(a.csv)
    if a.list_columns:
        print(f"행 수 {len(raw)}")
        for c in raw.columns:
            print(f"- {c}: 예시 {raw[c].dropna().astype(str).unique()[:5].tolist()}")
        return 0

    for need in ("name_col", "address_col", "atm_col", "atm_pattern"):
        if not getattr(a, need):
            raise SystemExit(f"--{need.replace('_', '-')} 가 필요합니다. 먼저 --list-columns 로 확인하세요.")

    regions = pd.read_csv(
        ROOT / "data" / "raw" / f"seoul_districts_{config.DATASET_VERSION}.csv",
        dtype={"region_code": str},
    )
    spec = PrepSpec(
        name_col=a.name_col, address_col=a.address_col,
        atm_col=a.atm_col, atm_pattern=a.atm_pattern, type_col=a.type_col,
    )
    res = prepare_v5(raw, regions, spec)

    print("== 단계별 행 수 ==")
    for name, n in res.steps:
        print(f"{name}: {n}")
    print("== 메모 ==")
    for n in res.notes:
        print(f"- {n}")

    if not res.ok:
        print("\n기대와 달라 파일을 만들지 않았습니다. 위 차이를 확인하세요.")
        return 2
    if a.dry_run:
        print("\n--dry-run: 조건 충족, 파일은 저장하지 않았습니다.")
        return 0

    out = ROOT / "data" / "raw" / f"ibk_branches_{OUTPUT_VERSION}.csv"
    if out.exists():
        raise SystemExit(f"이미 있는 파일은 덮어쓰지 않습니다: {out}")
    res.table.to_csv(out, index=False, encoding="utf-8")
    print(f"\n저장: {out}")
    print(f"적용하려면 config.BRANCH_DATASET_VERSION = \"{OUTPUT_VERSION}\" 로 바꾸세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
