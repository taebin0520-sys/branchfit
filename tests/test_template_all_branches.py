"""실제 v5 데이터 181개 점포 전체에서 템플릿 브리핑이 검증을 통과하는지 확인합니다.

검증기 금지 패턴을 늘린 뒤, 정상 템플릿 문장이 오탐으로 막히지 않는지 보는 회귀 테스트입니다.
"""

from branchfit import briefing, pipeline, validator


def test_template_briefing_passes_for_every_real_branch():
    regions, branches = pipeline.build_tables()
    failures = []
    for branch_id in branches["branch_id"]:
        contract = pipeline.build_contract_for_branch(regions, branches, branch_id)
        result = validator.validate(briefing.build_template_briefing(contract), contract)
        if not result.ok:
            failures.append((branch_id, result.errors))
    assert len(branches) == 181
    assert not failures, failures[:3]
