"""v5 변환 로직 테스트. 가상 행만 사용합니다(실제 점포 아님)."""

import pandas as pd

from branchfit.branch_prep import PrepSpec, prepare_v5

REGIONS = pd.DataFrame({
    "region_code": ["11110", "11140"],
    "region_name": ["종로구", "중구"],
    "ibk_branches": [2, 1],
})


def _raw():
    return pd.DataFrame({
        "점포명": ["가지점", "나지점", "다지점", "기업금융센터A", "ATM기기1", "부산지점"],
        "주소": [
            "서울특별시 종로구 1", "서울특별시 종로구 2", "서울특별시 중구 3",
            "서울특별시 중구 4", "서울특별시 종로구 5", "부산광역시 중구 6",
        ],
        "구분": ["영업점", "영업점", "영업점", "영업점", "현금자동입출금기", "영업점"],
    })


def _spec(**kw):
    base = dict(name_col="점포명", address_col="주소", atm_col="구분",
                atm_pattern="현금자동", expected_after_atm=4, expected_final=3)
    base.update(kw)
    return PrepSpec(**base)


def test_filter_steps_and_ids():
    res = prepare_v5(_raw(), REGIONS, _spec())
    assert res.steps == [("원본", 6), ("① 서울", 5), ("② ATM 제외", 4), ("③ 기업금융센터 제외", 3)]
    assert res.ok
    assert res.table["branch_id"].tolist() == ["IBK-11110-01", "IBK-11110-02", "IBK-11140-01"]
    assert (res.table["coord_status"] == "missing").all()
    assert res.table["lat"].isna().all()


def test_count_mismatch_is_reported_not_forced():
    res = prepare_v5(_raw(), REGIONS, _spec(expected_final=182))
    assert not res.ok
    assert any("기대 182건, 실제 3건" in n for n in res.notes)


def test_missing_column_is_reported():
    res = prepare_v5(_raw(), REGIONS, _spec(atm_col="없는컬럼"))
    assert res.table is None and not res.ok
    assert any("컬럼 없음" in n for n in res.notes)
