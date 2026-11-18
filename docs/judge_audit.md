# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Confusion (`tp/fp/fn/tn`) | Fail rate (obs → RG) | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|---|---|
| `tone_ok` (`judge_tone_public.csv`) | 100 | 0.757 | 0.857 | 0.800 | `tp=24, fp=4, fn=6, tn=66` | `0.28 → 0.30` | **Đạt** (`0.757≥0.6`, `0.857≥0.8`, `0.800≥0.7`) | **dùng** |
| `helpful` (`judge_helpful_public.csv`) | 100 | 0.375 | 1.000 | 0.300 | `tp=9, fp=0, fn=21, tn=70` | `0.09 → 0.30` | **Không đạt** (`κ=0.375<0.6`, `R=0.300<0.7`) | **loại** |

## ≥5 case audit thủ công
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú & Hành động sửa Rubric |
|---|---|---|---|---|---|
| 1 | `H-008` (`tone_ok`) | `PASS` | `FAIL` | **Người đúng** | Reply: *"Em đã hoàn tiền cho anh rồi nha, anh check giúp em."* Xưng `"em"` + `"nha"` quá suồng sã; judge coi là thân thiện. **Sửa rubric:** Bắt buộc xưng `"LogiX"` – `"anh/chị"`, cấm đại từ `"em"`, `"bạn"` và tiểu từ khẩu ngữ `"nha"`, `"nhé"`. |
| 2 | `H-017` (`tone_ok`) | `PASS` | `FAIL` | **Người đúng** | Reply: *"Dạ, bạn ơi LogiX đã hoàn 25.000đ cho đơn O-606 rồi nha."* Xưng `"bạn ơi"` + `"nha"` sai chuẩn CSKH LogiX. **Sửa rubric:** Thêm quy tắc từ chối (`FAIL`) mọi câu dùng `"bạn"` / `"bạn ơi"` thay vì `"anh/chị"`. |
| 3 | `H-029` (`tone_ok`) | `PASS` | `FAIL` | **Người đúng** | Reply: *"Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm."* Giọng mệnh lệnh, đuổi khách ở vế `"không cần nhắn thêm"`; judge bị đánh lừa bởi từ mở đầu `"Dạ, vui lòng"`. **Sửa rubric:** Đánh giá toàn bộ câu, cấm các mệnh lệnh cấm đoán khách (`"không cần nhắn thêm"`, `"khỏi hỏi nữa"`). |
| 4 | `H-042` (`tone_ok`) | `FAIL` | `PASS` | **Người đúng** | Reply: *"Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ."* Câu ngắn gọn, lịch sự, đủ thông tin nhưng judge phạt vì thiếu câu xin lỗi. **Sửa rubric:** Không bắt buộc phải có câu xin lỗi dài dòng khi thông báo kết quả hoàn tiền thành công nếu đã có `"Dạ ... ạ"`. |
| 5 | `H-051` (`tone_ok`) | `FAIL` | `PASS` | **Người đúng** | Reply: *"Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ."* Judge phạt vì dùng thuật ngữ tiếng Anh `"refund"`, trong khi CSKH LogiX cho phép. **Sửa rubric:** Cho phép thuật ngữ `"refund"` tương đương `"hoàn tiền"` trong câu lịch sự. |
| 6 | `H-063` (`tone_ok`) | `PASS` | `FAIL` | **Người đúng** | Reply: *"Dạ, LogiX đã hoàn 20.000đ và sẽ hoàn thêm cho anh/chị ạ."* Tự ý hứa hẹn `"sẽ hoàn thêm"` ngoài kết quả hệ thống. **Sửa rubric:** Đánh `FAIL` nếu reply tự hứa hoàn thêm tiền hoặc cam kết ngoài quyết định đã chốt. |
| 7 | `H-070` (`tone_ok`) | `PASS` | `FAIL` | **Người đúng** | Reply: *"Dạ, LogiX đã hoàn 90.000đ cho đơn O-909 ạ 😂😂"* Dùng emoji `😂😂` cợt nhả trong ngữ cảnh xử lý khiếu nại. **Sửa rubric:** Cấm tuyệt đối emoji không trang trọng trong phản hồi khiếu nại. |
| 8 | `H-081` (`tone_ok`) | `FAIL` | `PASS` | **Judge đúng** | Reply: *"Dạ, đơn O-107 chưa đủ điều kiện hoàn theo chính sách hiện hành ạ."* Người gán nhãn đọc nhầm ticket nên gán sai; **Hành động:** Sửa lại nhãn chuẩn (`gold label`) của `H-081` và rà soát quy trình gán nhãn của người. |
| 9 | `H-094` (`tone_ok`) | `PASS` | `FAIL` | **Người đúng** | Reply: *"Da, LogiX da hoan 40.000đ cho don O-341, xin loi vi su bat tien."* Văn bản mất dấu tiếng Việt. **Sửa rubric:** Bắt buộc tiếng Việt có dấu đầy đủ, đánh `FAIL` nếu câu trả lời không dấu. |
| 10 | `HL-015`, `HL-016` (`helpful`) | `PASS` | `FAIL` | **Người đúng** | Reply nói hoàn `55.000đ` nhưng ledger chỉ ghi `40.000đ` / `35.000đ` (`FM-08`), được bọc trong lời xin lỗi rất dài dòng. Judge bị **verbosity/politeness bias** và không đối chiếu được dữ liệu số học trên ledger. **Hành động:** Loại bỏ LLM judge `helpful` khỏi CI gate; chuyển việc kiểm tra khớp số tiền `reply` vs `ledger` sang **code grader** (`ReplyAmountMatch`). |

## Kết luận
- **Tiêu chí bị loại và lý do:** Loại bỏ judge **`helpful`** (`judge_helpful_public.csv`) vì **không đạt ngưỡng calibration** (`κ = 0.375 < 0.6`, `Recall = 0.300 < 0.7`, dù `Precision = 1.0`). Ma trận nhầm lẫn `{'tp': 9, 'fp': 0, 'fn': 21, 'tn': 70}` cho thấy judge bỏ lọt tới **21/30 ca lỗi thực tế (`fn = 21`)**, khiến tỉ lệ lỗi quan sát được chỉ là `9.0%` trong khi tỉ lệ lỗi thực tế sau hiệu chỉnh Rogan-Gladen là `30.0%`. Trong 21 ca bỏ lọt (`fn`), có tới **18 ca là lỗi báo sai số tiền (`sai tiền` / `FM-08`)** được che đậy bằng văn phong xin lỗi dài dòng (thiên kiến độ dài / *verbosity bias*). Quy tắc cốt lõi: **tiền và phê duyệt luôn phải chấm bằng code (`RefundAmountCorrect`, `ReplyAmountMatch`), tuyệt đối không dùng LLM judge làm gate cho tính đúng đắn của số tiền.**
- **Tiêu chí được giữ lại:** Judge **`tone_ok`** đạt cả 3 ngưỡng (`κ = 0.757 ≥ 0.6`, `P = 0.857 ≥ 0.8`, `R = 0.800 ≥ 0.7`, ma trận nhầm lẫn `{'tp': 24, 'fp': 4, 'fn': 6, 'tn': 66}`, tỉ lệ lỗi quan sát `0.28` → hiệu chỉnh Rogan-Gladen `0.30`), đủ điều kiện dùng cho tiêu chí văn phong sau khi cập nhật rubric (xưng hô, tiếng Việt có dấu, cấm emoji/mệnh lệnh).
- **Rủi ro còn lại:** Judge chỉ mới được kiểm định trên tập dữ liệu replay đã công khai (`n = 100`); nếu tinh chỉnh rubric dựa trên chính 100 mẫu này sẽ có nguy cơ overfit vào tập calibration, nên bắt buộc phải thu thập nhãn người mới trên một tập **held-out độc lập** trước khi đưa vào vận hành thật.
