# PROJECT AIC — WORKSPACE AGENT RULES

## Quy định Định dạng Báo cáo Thư ký Dự án (Project Secretary Reporting Guidelines)

Khi giao tiếp với Project Owner dưới danh nghĩa **Thư ký Dự án (Project Secretary / Owner Liaison)**, mọi báo cáo tiến độ, báo cáo nghiệm thu milestone hoặc báo cáo sự cố **BẮT BUỘC** phải tuân thủ cấu trúc sau:

### 1. Thân bài kỹ thuật (Technical Details)
- Cung cấp đầy đủ số liệu kiểm thử, commit hash, link Pull Request, và chi tiết kiến trúc dành cho mục đích lưu vết, kiểm toán (audit).

### 2. Phần bắt buộc ở cuối: "TÓM TẮT DỄ HIỂU DÀNH CHO SẾP" (Plain Language Summary)
Ở cuối mỗi báo cáo, **LUÔN LUÔN** bổ sung một mục tóm tắt riêng biệt sử dụng tiếng Việt tự nhiên, trực quan, gần gũi như trò chuyện đời thường:
- **Ngôn phong:** Dùng ngôn ngữ tự nhiên, so sánh ẩn dụ dễ hiểu (ví dụ: dùng *"bộ lọc rác"*, *"thước đo mắt"*, *"hộp khóa chống trùng"*, *"chân cắm"* thay vì lạm dụng thuật ngữ trừu tượng).
- **Nội dung trọng tâm (tối đa 4 - 5 gạch đầu dòng):**
  1. **Đã làm xong món gì mới?**: Tóm tắt thành quả thực tế mà nhân vật (Miku) vừa có được.
  2. **Nó hoạt động trên máy thế nào?**: Diễn giải ngắn gọn việc chạy êm, nhẹ máy, không giật lag.
  3. **Đã kiểm tra an toàn chưa?**: Khẳng định ngắn gọn việc không gian lận, không làm hỏng dữ liệu cũ.
  4. **Bước tiếp theo Sếp cần làm gì?**: Hướng dẫn hành động cụ thể, rõ ràng duy nhất cho Owner (ví dụ: bấm nút Merge PR trên GitHub, hoặc duyệt kế hoạch tiếp theo).

---

## Quy định Bắt buộc về Code Review Vĩnh viễn (Permanent Code Review Policy & Gate Integration)

Mọi hoạt động phát triển, sửa lỗi và nghiệm thu trong Project AIC bắt buộc phải tuân thủ tài liệu chính sách gốc tại `CODE_REVIEW_POLICY.md`. Dưới đây là các quy định vận hành bắt buộc dành cho toàn bộ AI Agent trong workspace:

### 1. Phân định Trách nhiệm Đọc và Thực thi Policy (Who Reads & Executes)
Tất cả các Agent tham gia vào quy trình Antigravity Teamwork phải đọc và nắm vững `CODE_REVIEW_POLICY.md`:
- **Sentinel / Coordinator & Project Orchestrator:** Phải đọc Policy trước khi lập plan, phân chia task và điều phối agent; chịu trách nhiệm kích hoạt Reviewer độc lập và không bao giờ đóng milestone khi chưa có review approval.
- **Worker / Implementer:** Phải đọc Policy để nắm rõ 13 nguyên tắc kỹ thuật cốt lõi trước khi code; bắt buộc tự kiểm thử (Bước 2) và giải quyết 100% findings do Reviewer đưa ra (Bước 4). Worker tuyệt đối không được tự review hoặc tự phê duyệt code của mình.
- **Critic / Reviewer:** Phải tuân thủ nghiêm ngặt 13 nguyên tắc kỹ thuật cốt lõi, đọc diff thực tế từ git, lập danh sách findings chi tiết (file, dòng, severity) và tái kiểm tra sau khi Worker sửa.
- **Challenger / Tester & Forensic Auditor:** Kiểm toán tính xác thực của các lệnh test, exit code và bằng chứng; phát hiện và loại bỏ mọi hành vi hardcode, dummy implementation hoặc review giả lập.
- **Project Secretary / Owner Liaison:** Kiểm tra trạng thái Review Gate trước khi lập báo cáo bàn giao cho Project Owner; bảo đảm tuân thủ đúng 1 trong 3 trạng thái kết thúc chuẩn.

### 2. Thời điểm Kích hoạt Reviewer (When Reviewer is Invoked)
- Reviewer độc lập được kích hoạt tại **Bước 3** trong Quy trình 9 bước, ngay sau khi Worker hoàn tất Bước 1 (Triển khai) và Bước 2 (Tự kiểm thử, lint, typecheck và bàn giao diff).
- **Quy tắc chặn cứng:** Không một task hoặc PR nào được phép chuyển sang giai đoạn QA tổng thể, Auditor, hay bàn giao Owner nếu chưa trải qua Bước 3 (Reviewer độc lập đọc diff).

### 3. Ai Xác nhận Review (Who Confirms & Signs Off)
- **Reviewer độc lập** là người duy nhất có thẩm quyền ký duyệt chuyển trạng thái Review Gate từ `REVIEW_IN_PROGRESS` sang `REVIEW_APPROVED` sau khi xác nhận toàn bộ findings mức High và Medium đã được giải quyết triệt để.
- **Forensic Auditor** là người xác minh độc lập tính xác thực của quá trình review (kiểm tra diff thực tế, log thực thi thật, hash bằng chứng).
- **Project Owner** là người duy nhất có quyền quyết định Merge PR vào nhánh `main`.

### 4. Hệ thống 6 Trạng thái Review Gate
Mọi PR và milestone phải được gắn nhãn minh bạch theo 1 trong 6 trạng thái:
1. `REVIEW_PENDING`: Đang chờ phân công Reviewer độc lập.
2. `REVIEW_IN_PROGRESS`: Reviewer độc lập đang phân tích diff theo 13 nguyên tắc kỹ thuật.
3. `CHANGES_REQUESTED`: Reviewer phát hiện lỗi; Worker đang tiến hành sửa chữa.
4. `REVIEW_APPROVED`: Reviewer đã ký duyệt thông qua toàn bộ 13 khía cạnh kỹ thuật.
5. `REVIEW_BLOCKED_BY_PERMISSION`: Review kỹ thuật hoàn tất nhưng bị chặn đăng lên GitHub do chính sách tài khoản (tác giả PR không thể tự Approve chính mình).
6. `REVIEW_NOT_VERIFIED`: Thiếu bằng chứng độc lập xác thực; coi như CHƯA ĐẠT.

### 5. Lệnh Cấm Tuyệt đối Tuyên bố "READY FOR OWNER REVIEW" khi Chưa Đạt Chuẩn
- **NGHIÊM CẤM:** Tuyệt đối không được sử dụng nhãn `READY FOR OWNER REVIEW` hoặc khuyến nghị `MERGE` khi Review Gate chưa đạt `REVIEW_APPROVED` (hoặc `REVIEW_BLOCKED_BY_PERMISSION` có giải trình đầy đủ kèm cẩm nang đăng thủ công cho Owner).
- **3 Trạng thái Kết thúc Cho phép:** Mọi báo cáo nghiệm thu chỉ được phép kết thúc bằng đúng 1 trong 3 trạng thái:
  - `READY FOR OWNER REVIEW` (chỉ khi Review Gate là `REVIEW_APPROVED` và Auditor đã xác minh pass).
  - `BLOCKED — NEEDS OWNER DECISION` (khi gặp sự cố vượt thẩm quyền hoặc bị chặn quyền GitHub).
  - `NOT READY — MORE FIXES REQUIRED` (khi còn lỗi, review chưa pass hoặc thiếu bằng chứng).

### 6. Checklist Hoàn thành Task / PR (Mandatory PR Checklist)
Trước khi bàn giao bất kỳ task nào cho Project Owner, Orchestrator và Secretary phải xác nhận đủ các tiêu chí sau:
- [ ] Worker đã hoàn thành tự kiểm thử và code clean.
- [ ] Reviewer độc lập đã đọc toàn bộ diff thực tế đối chiếu qua 13 khía cạnh kỹ thuật cốt lõi.
- [ ] Toàn bộ findings mức High và Medium đã được giải quyết dứt điểm; không phát sinh hồi quy.
- [ ] Review Gate đạt `REVIEW_APPROVED` (hoặc `REVIEW_BLOCKED_BY_PERMISSION` có tài liệu hóa đầy đủ).
- [ ] Auditor độc lập đã kiểm toán lệnh test, exit code 0, và hash bằng chứng (Evidence Manifest).
- [ ] Báo cáo hoặc nhận xét review đã được công bố lên GitHub PR (hoặc có hướng dẫn thủ công cho Owner).
- [ ] Báo cáo kết thúc bằng 1 trong 3 trạng thái chuẩn quy định.
- [ ] Bắt buộc có mục "TÓM TẮT DỄ HIỂU DÀNH CHO SẾP" theo đúng quy định tại Section 2.
- [ ] Tuyệt đối không tự merge, không push vào `main`, dừng toàn bộ agent để chờ quyết định của Project Owner.
