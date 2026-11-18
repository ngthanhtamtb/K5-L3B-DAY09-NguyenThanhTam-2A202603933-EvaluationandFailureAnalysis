# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Mẫu điền (mỗi bạn 1 case, lấy từ trial đang fail trong report)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, run ID `E-seeded_regression-20261118-0139` (và `swarm C-002@55`, trace `traces/R-swarm-C-002-s55.json`) |
| Triệu chứng | `TrialPass` (`pass_rate`), `RefundAmountCorrect` (`refund_amount_correct`) và `DbFactKept` (`db_fact_kept`) đều FAIL; `reply` nói `"Dạ, LogiX đã hoàn 20.000đ cho đơn O-202."` và ledger ghi `refund_vnd=20000`, `refund_count=1` trong khi nhãn đúng là `status="denied"`, `refund_vnd=0`, `refund_count=0`. |
| Bước sai đầu tiên | Event `#3` · `model_override` · `{"delay_days": 5}` |
| Vì sao là bước *đầu tiên* | Event `#1` (`handoff`) khởi tạo phạm vi `owner_order_only` đúng; Event `#2` (`investigator`) truy vấn DB và trả về dữ liệu chuẩn `{"order_id": "O-202", "status": "delivered", "delay_days": 2, "shipping_fee_vnd": 20000}`. Phải đến Event `#3` (`model_override`), agent mới lấy số ngày `5` trong ticket của khách đè lên `delay_days=2` của DB, kéo theo Event `#4` (`quote`) tính sai `amount_vnd=20000` theo `SHIP-LATE-03`. |
| Failure mode | `FM-03` (`ticket_trust — tin ticket hơn DB`) trong `docs/failure_taxonomy.md` |
| Đối chứng | Cùng `C-002@11` trên shape `fixed`: sau Event `#2` (`investigator` trả `delay_days=2`), **không có** event `model_override`; Event `#3` (`quote`) giữ nguyên `delay_days=2` nên trả `{"amount_vnd": 0, "reason": "not_eligible", "clause_ids": [], "parts": {}}`, và Event `#4` (`reply`) từ chối đúng chính sách (`ledger refund_vnd=0`, `status="denied"`). |
| Regression test | `tests/test_lab9_graders.py::test_override_event_breaks_db_fact`, `tests/test_lab9_graders.py::test_wrong_amount_in_ledger`, và `tests/test_lab9_graders.py::test_trace_case_c002_regression` (kiểm tra `DbFactKept` và `RefundAmountCorrect` fail trên `seeded_regression C-002@11` và pass trên `fixed C-002@11`). |
| Chưa chắc chắn | Trace chỉ ghi nhận sự kiện `model_override` với `{"delay_days": 5}` mà không lưu toàn bộ raw prompt/response nội bộ của bước `parse_delay_days`, nên nếu biến thể `quiet_override` bỏ ghi event `model_override` thì `DbFactKept` (step-level) sẽ không thấy, bắt buộc phải có `RefundAmountCorrect` (outcome-level trên ledger) để chặn. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
