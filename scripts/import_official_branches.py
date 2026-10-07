"""Rebuild the Seoul fixed-branch sample from public CSV 15006875."""
from pathlib import Path
import hashlib
import json
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
VERSION = "2026-10-08_v5"
SOURCE = ROOT / "data/source/ibk_branch_details_20251231.csv"


def main():
    raw = pd.read_csv(SOURCE, dtype=str)
    required = {"점포명", "주소", "전화번호"}
    if not required.issubset(raw.columns):
        raise ValueError("점포명세 원본 컬럼 불일치")
    for col in ("점포명", "주소"):
        if raw[col].isna().any():
            raise ValueError(f"{col} 누락")
        raw[col] = raw[col].str.strip()
    seoul = raw[raw["주소"].str.startswith("서울특별시 ")].copy()
    excluded = seoul[seoul["점포명"].str.contains("기업금융센터|^이동점포", regex=True)].copy()
    selected = seoul.drop(excluded.index).copy()
    regions = pd.read_csv(ROOT / "data/raw/seoul_districts_2026-09-19_v4.csv", dtype={"region_code": str})
    codes = regions.set_index("region_name")["region_code"].to_dict()
    selected["region_name"] = selected["주소"].str.split().str[1]
    selected["region_code"] = selected["region_name"].map(codes)
    if selected["region_code"].isna().any() or selected.duplicated(["점포명", "주소"]).any():
        raise ValueError("구 매핑 또는 중복 점포 오류")
    selected = selected.sort_values(["region_code", "점포명", "주소"]).reset_index(drop=True)
    out = pd.DataFrame({
        "branch_id": [f"IBK-{code}-{n:02d}" for code, n in zip(selected["region_code"], selected.groupby("region_code").cumcount()+1)],
        "branch_name": selected["점포명"],
        "branch_type": selected["점포명"].map(lambda n: "출장소" if n.endswith("(출)") else "영업점"),
        "region_code": selected["region_code"], "region_name": selected["region_name"],
        "address": selected["주소"], "name_source": "official", "source_date": "2025-12-31",
        "source_id": "15006875",
    })
    before = regions.set_index("region_name")["ibk_branches"]
    counts = out.groupby("region_name").size()
    regions["ibk_branches"] = regions["region_name"].map(counts).fillna(0).astype(int)
    regions["biz_count_status"] = "confirmed_table_pending"
    regions["data_status"] = "mixed_verification_pending"
    regions["ibk_source_date"] = "2025-12-31"
    regions.to_csv(ROOT / f"data/raw/seoul_districts_{VERSION}.csv", index=False)
    out.to_csv(ROOT / f"data/raw/ibk_branches_{VERSION}.csv", index=False)
    manifest = {
        "source_url": "https://www.data.go.kr/data/15006875/fileData.do",
        "source_date": "2025-12-31", "retrieved_date": "2026-10-08",
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "source_rows": len(raw), "seoul_rows": len(seoul), "fixed_branch_rows": len(out),
        "exclusion_rule": "기업금융센터 및 이동점포 제외; ATM 파일은 입력하지 않음",
        "excluded_rows": excluded[["점포명", "주소"]].to_dict(orient="records"),
        "district_count_changes": {name: {"before": int(before[name]), "after": int(counts.get(name, 0))}
                                   for name in before.index if before[name] != counts.get(name, 0)},
        "biz_count_status": "기존 값 유지; 시군구 확정 통계표 대조 필요",
        "current_operations_status": "기준일 이후 운영·주소 변경 미확인",
    }
    (ROOT / "data/source/manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
