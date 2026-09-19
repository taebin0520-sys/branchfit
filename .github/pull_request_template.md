## 무엇을 바꿨나

<!-- 기획서의 어느 절에 해당하는 변경인지 함께 적어주세요 -->

## 데이터 영향

- [ ] `dataset_version` 변경 여부: 변경됨 / 변경 없음
- [ ] `data/raw/` 수치 변경 여부: 변경됨 / 변경 없음
- [ ] `data_status`, `name_source` 값이 실제 상태와 일치하는가 (`placeholder` / `official`)

## 검증

```bash
python scripts/selfcheck.py   # 결과 붙여넣기
pytest -q                     # 결과 붙여넣기
```

## 가드레일 확인 (AI 관련 변경 시)

- [ ] 템플릿 fallback이 여전히 검증을 통과한다 (selfcheck의 "182개 전 점포" 항목)
- [ ] 금지표현·수치대조·고유명 검출 규칙을 느슨하게 만들지 않았다
- [ ] 통·폐합 판정/추천에 해당하는 표현을 추가하지 않았다
