# PROJECT AIC — PERMANENT CODE REVIEW POLICY & GATE SPECIFICATION

**Phiên bản:** 1.0  
**Ngày ban hành:** 09/11/2026  
**Trạng thái:** BẮT BUỘC ÁP DỤNG VĨNH VIỄN (MANDATORY & ENFORCED)  
**Phạm vi áp dụng:** Toàn bộ repository `Project-AIC`, tất cả Pull Requests, và mọi AI Agent trong Google Antigravity Teamwork.

---

## 1. Mục đích và Ranh giới Cốt lõi (Purpose & Scope)

Tài liệu này thiết lập **Chính sách Code Review Vĩnh viễn (Permanent Code Review Policy)** nhằm đảm bảo mọi thay đổi mã nguồn trong Project AIC đều phải trải qua quá trình kiểm tra kỹ thuật độc lập, thực chất, có bằng chứng xác thực và không thể gian lận.

### Các nguyên tắc nền tảng:
1. **Không có Code Review, không có Merge:** Mọi Pull Request (PR) muốn được đưa vào nhánh `main` bắt buộc phải có báo cáo Code Review độc lập được phê duyệt.
2. **Reviewer phải hoàn toàn độc lập với Worker:** Agent viết code (Worker/Implementer) tuyệt đối không được tự review hoặc tự đóng dấu chấp thuận (self-approval) cho code của chính mình.
3. **Review trên diff thực tế, không review trên báo cáo:** Reviewer phải đọc từng dòng lệnh thay đổi (`git diff`), kiểm tra logic, chạy thử hoặc xác minh lệnh kiểm thử; không được dựa vào tóm tắt của Worker hay báo cáo benchmark để suy diễn chất lượng mã nguồn.
4. **Cấm tuyệt đối gian lận và tạo bằng chứng giả:** Mọi nhận xét review, log kiểm thử, hash SHA-256 phải là dữ liệu thật. Không được làm giả kết quả kiểm thử, không hardcode giá trị để qua mặt bài test.

---

## 2. Quy trình Review 9 Bước Bắt buộc (Mandatory 9-Step Workflow)

Mỗi tính năng hoặc bản sửa lỗi từ khi bắt đầu triển khai đến khi hoàn thành phải tuân thủ nghiêm ngặt 9 bước tuần tự sau:

```
[1. Worker Triển khai] 
         │
         ▼
[2. Worker Tự kiểm thử & Self-Check]
         │
         ▼
[3. Kích hoạt Reviewer Độc lập] ◄──────┐
         │                             │ (Nếu có lỗi)
         ▼                             │
[4. Worker Xử lý Sửa đổi (Fixes)] ─────┘
         │ (Khi đã sửa xong)
         ▼
[5. Reviewer Tái kiểm tra (Recheck)]
         │
         ▼
[6. Review Đạt chuẩn (Review Accepted)]
         │
         ▼
[7. QA / Challenger / Auditor Xác minh]
         │
         ▼
[8. Công bố Review lên GitHub (Published / Documented)]
         │
         ▼
[9. Project Owner Review & Quyết định Merge]
```

### Chi tiết các bước:

### Bước 1: Worker Triển khai (Worker Implementation)
- Worker thực hiện viết code tính năng hoặc sửa lỗi trên branch riêng biệt (ví dụ: `feature/*`, `fix/*`).
- Chỉ sửa trong phạm vi thư mục/file được phân công; tuân thủ kiến trúc mô tả trong `docs/AIC_ARCHITECTURE_v0.5.md` và SRS `docs/AIC_SRS_v0.5.md`.
- Viết kèm unit test cơ sở để bảo đảm chức năng hoạt động.

### Bước 2: Worker Tự kiểm thử & Self-Check (Worker Self-Test & Preflight)
- Worker tự chạy toàn bộ test liên quan, linting và type checking.
- Kiểm tra `git status` và `git diff` để đảm bảo không commit nhầm secret, token, runtime database, model weights hoặc file rác.
- Tạo Pull Request ở trạng thái **Draft PR** trên GitHub (nếu có quyền) hoặc bàn giao diff cho Coordinator.
- Trạng thái Review Gate lúc này là: `REVIEW_PENDING`.

### Bước 3: Kích hoạt Reviewer Độc lập (Independent Code Review Invocation)
- Project Orchestrator/Coordinator chỉ định một Agent riêng biệt mang vai trò **Reviewer / Critic** (hoàn toàn tách biệt với Worker).
- Reviewer kiểm tra HEAD commit SHA thực tế của PR so với base commit SHA.
- Reviewer phân tích toàn diện diff thực tế dựa trên **13 Nguyên tắc Đánh giá Kỹ thuật Cốt lõi** (xem Mục 3).
- Trạng thái Review Gate chuyển thành: `REVIEW_IN_PROGRESS`.

### Bước 4: Worker Xử lý Sửa đổi (Worker Remediation / Fixes)
- Nếu Reviewer phát hiện lỗi hoặc rủi ro (đặc biệt các mức High / Medium), Reviewer xuất danh sách findings cụ thể (gồm file, dòng code, mô tả lỗi và hướng xử lý).
- Trạng thái Review Gate chuyển thành: `CHANGES_REQUESTED`.
- Worker nhận danh sách findings, thực hiện sửa chữa code theo nguyên tắc thay đổi tối thiểu, cập nhật test và chạy lại test suite.
- Worker không được tự ý bỏ qua finding mà không có lý lẽ kỹ thuật kèm bằng chứng xác thực.

### Bước 5: Reviewer Tái kiểm tra (Reviewer Recheck & Diff Verification)
- Reviewer kiểm tra lại diff mới nhất sau khi Worker đã sửa.
- Xác nhận từng finding đã được giải quyết triệt để và không phát sinh hồi quy (regression).

### Bước 6: Review Đạt chuẩn (Review Accepted & Sign-off)
- Khi toàn bộ finding mức High và Medium đã được giải quyết dứt điểm và không còn rủi ro kiến trúc, Reviewer ký duyệt nghiệm thu review.
- Trạng thái Review Gate chuyển thành: `REVIEW_APPROVED`.

### Bước 7: QA / Challenger / Auditor Xác minh (Independent QA & Forensic Validation)
- Challenger chạy các bài test đối kháng (stress test, edge cases, invalid inputs).
- Teamwork Auditor kiểm toán tính xác thực của các lệnh test, exit code 0, và hash bằng chứng (Evidence Manifest).
- Xác minh không có code giả lập (facade/dummy) hay hardcoded output.

### Bước 8: Công bố Review lên GitHub (GitHub Review Publication & Reporting)
- Đăng kết quả review lên GitHub Pull Request theo đúng cơ chế phân quyền (xem Mục 5).
- Nếu bị giới hạn bởi quyền hạn tài khoản (ví dụ: tác giả PR không thể tự Approve chính mình trên GitHub), phải ghi nhận trạng thái `REVIEW_BLOCKED_BY_PERMISSION` hoặc đăng dưới dạng Issue Comment và cung cấp cẩm nang đăng thủ công đầy đủ cho Project Owner.

### Bước 9: Project Owner Review & Quyết định Merge (Owner Review & Merge Decision)
- Project Secretary / Owner Liaison tổng hợp toàn bộ hồ sơ, kèm mục bắt buộc **"TÓM TẮT DỄ HIỂU DÀNH CHO SẾP"**.
- Trình nộp lên Project Owner. **CHỈ CÓ DUY NHẤT PROJECT OWNER MỚI CÓ QUYỀN RA QUYẾT ĐỊNH MERGE.**
- Tuyệt đối cấm mọi Agent tự merge, dùng `--admin`, hoặc bật auto-merge khi chưa có phê duyệt bằng văn bản từ Owner.

---

## 3. Mười ba (13) Nguyên tắc Đánh giá Kỹ thuật Cốt lõi (13 Core Review Principles)

Mọi quá trình Code Review cho module AI pipeline, xử lý GPU, và backend trong Project AIC bắt buộc phải đối chiếu qua 13 khía cạnh kỹ thuật sau:

| # | Khía cạnh Kỹ thuật | Trọng tâm Đánh giá & Ranh giới Nghiêm ngặt |
|---|---|---|
| **1** | **DirectML Execution Provider** | Kiểm tra cấu hình provider `DmlExecutionProvider`, thứ tự ưu tiên provider list, device ID chính xác, xử lý trường hợp thư viện DirectML thiếu hoặc không tương thích. |
| **2** | **Device Discovery & Adapter Mapping** | Xác minh cơ chế phát hiện GPU (đặc biệt NVIDIA GeForce RTX 4050 Laptop GPU / DXGI / Direct3D 12 adapter index). Đảm bảo không hardcode index thiết bị khiến crash trên máy khác. |
| **3** | **CPU Fallback Robustness** | Kiểm tra khả năng tự động fallback về `CPUExecutionProvider` khi khởi tạo DirectML thất bại hoặc gặp lỗi runtime. Fallback phải an toàn, ghi log cảnh báo rõ ràng, không làm gián đoạn ứng dụng. |
| **4** | **ONNX Runtime & Provider Compatibility** | Đối chiếu tính tương thích giữa phiên bản `onnxruntime` / `onnxruntime-directml`, tránh xung đột wheel, tương thích ABI và driver DirectX/DirectML trên Windows 11. |
| **5** | **Session Lifecycle Management** | Đánh giá quá trình khởi tạo InferenceSession, warm-up run, tái sử dụng session, và giải phóng tài nguyên. Tránh re-create session liên tục gây lãng phí VRAM. |
| **6** | **Concurrency, Mutex & Deadlock** | Đảm bảo tính an toàn đa luồng (thread-safety) khi FastAPI xử lý nhiều request đồng thời gọi vào cùng một ONNX session. Kiểm tra thứ tự lock (lock ordering) và timeout để loại trừ triệt để deadlock. |
| **7** | **Image Preprocessing & Postprocessing** | Kiểm tra định dạng màu (RGB vs BGR), kích thước tensor (chuẩn 1024x1024 cho IS-Net Anime), nội suy (bilinear/bicubic), chuẩn hóa giá trị pixel (mean/std), hàm kích hoạt sigmoid và ngưỡng binarization mask. |
| **8** | **Tensor Shape, Dtype & Memory Leaks** | Kiểm tra shape `[1, 3, 1024, 1024]`, kiểu dữ liệu `float32`, contiguous memory array trong RAM và VRAM. Đảm bảo giải phóng tensor sau inference, không rò rỉ bộ nhớ khi chạy batch dài hạn. |
| **9** | **Error Handling & Resource Cleanup** | Kiểm tra cấu trúc `try...except...finally`, bắt đúng exception chuyên biệt (ví dụ `OrtException`, `MemoryError`), dọn dẹp biến tạm và bộ nhớ GPU trong khối `finally`. Không nuốt exception âm thầm. |
| **10** | **CPU/DirectML Output Consistency** | So sánh sai số số học giữa kết quả inference trên CPU và DirectML. Đảm bảo độ tương đồng thị giác (visual parity) và sai số Mean Absolute Error (MAE) nằm trong ngưỡng dung sai kỹ thuật cho phép. |
| **11** | **Unit, Integration & Hardware Tests** | Đánh giá độ bao phủ của test suite: test mock cho môi trường không có GPU, test phần cứng thật khi có RTX 4050, test nhánh lỗi (failure paths), và kiểm tra exit code. |
| **12** | **Benchmark Correctness & Measurement Fairness** | Phân định rạch ròi phạm vi đo của timer: tách biệt hoàn toàn giữa `inference-only` (chỉ đo thời gian `session.run()`) và `end-to-end` (bao gồm tiền xử lý, nạp ảnh, hậu xử lý). Cấm gộp số đo hoặc thổi phồng speedup. |
| **13** | **Backward Compatibility** | Đảm bảo không phá vỡ hợp đồng API, cấu trúc `CharacterPack`, hoặc các interface đã thiết lập từ các task trước (như Task 0.5B-1). |

---

## 4. Hệ thống 6 Trạng thái Review Gate (6 Review Gate States)

Quá trình kiểm soát chất lượng mã nguồn được quản lý qua một State Machine gồm 6 trạng thái độc quyền:

```
┌─────────────────┐
│ REVIEW_PENDING  │ ──(Reviewer được chỉ định)──► ┌────────────────────┐
└─────────────────┘                               │ REVIEW_IN_PROGRESS │
                                                  └────────────────────┘
                                                             │
                    ┌────────────────────────────────────────┴────────────────────────────────────────┐
                    ▼                                                                                 ▼
          ┌───────────────────┐                                                             ┌─────────────────┐
          │ CHANGES_REQUESTED │ ◄──(Phát hiện lỗi cần sửa)                                  │ REVIEW_APPROVED │
          └───────────────────┘                                                             └─────────────────┘
                    │                                                                                 │
         (Worker sửa xong)                                                                            │
                    │                                                                                 │
                    ▼                                                                                 │
          ┌───────────────────┐                                                                       │
          │(Quay lại Bước 5)  │                                                                       │
          └───────────────────┘                                                                       │
                                                                                                      ▼
                                                          ┌──────────────────────────────────────────────────────────────┐
                                                          │ Nếu gặp sự cố xuất bản hoặc thiếu bằng chứng:                │
                                                          │ - REVIEW_BLOCKED_BY_PERMISSION (Lỗi quyền GitHub / Author)   │
                                                          │ - REVIEW_NOT_VERIFIED (Thiếu bằng chứng diff / log độc lập)   │
                                                          └──────────────────────────────────────────────────────────────┘
```

### Định nghĩa chi tiết các trạng thái:

1. **`REVIEW_PENDING` (Chờ Review):**
   - **Ý nghĩa:** Code đã được Worker triển khai và tự kiểm thử xong. PR đã tạo (hoặc diff đã sẵn sàng) nhưng chưa có Reviewer độc lập bắt đầu kiểm tra.
   - **Hành động tiếp theo:** Coordinator phân công Reviewer độc lập.

2. **`REVIEW_IN_PROGRESS` (Đang Thực hiện Review):**
   - **Ý nghĩa:** Reviewer độc lập đang đọc diff, chạy đối chiếu 13 nguyên tắc cốt lõi và kiểm tra test coverage.
   - **Hành động tiếp theo:** Reviewer lập danh sách findings và đưa ra kết luận sơ bộ.

3. **`CHANGES_REQUESTED` (Yêu cầu Sửa đổi):**
   - **Ý nghĩa:** Reviewer phát hiện lỗi logic, rủi ro bảo mật, nguy cơ rò rỉ tài nguyên, hoặc thiếu sót test cần Worker xử lý.
   - **Hành động tiếp theo:** Worker nhận task khắc phục, sửa đổi code và bàn giao lại cho Reviewer tái kiểm tra.

4. **`REVIEW_APPROVED` (Đã Thông qua Review):**
   - **Ý nghĩa:** Toàn bộ 13 khía cạnh kỹ thuật đã đạt yêu cầu; không còn bất kỳ finding mức High hoặc Medium nào chưa xử lý; test suite pass 100%.
   - **Hành động tiếp theo:** Chuyển sang bước kiểm toán QA/Auditor và chuẩn bị hồ sơ công bố.

5. **`REVIEW_BLOCKED_BY_PERMISSION` (Bị Chặn do Quyền hạn):**
   - **Ý nghĩa:** Đánh giá kỹ thuật đã hoàn tất và đạt chất lượng, nhưng việc gửi review submission chính thức lên GitHub bị từ chối do chính sách bảo mật của GitHub (ví dụ: tài khoản đang đăng nhập là Tác giả của PR, không thể tự Approve chính mình theo RFC của GitHub) hoặc token thiếu scope `write`.
   - **Hành động tiếp theo:** Ghi nhận minh bạch trong báo cáo, đăng tải advisory comment/issue comment nếu được phép, và cung cấp hướng dẫn thao tác thủ công từng bước cho Project Owner.

6. **`REVIEW_NOT_VERIFIED` (Chưa được Xác minh):**
   - **Ý nghĩa:** Không thể xác minh tính độc lập của reviewer, thiếu log thực thi gốc, SHA commit không khớp, hoặc bằng chứng bị nghi ngờ là tự tạo/suy đoán.
   - **Hành động tiếp theo:** BẮT BUỘC coi là CHƯA ĐẠT. Không được phép chuyển sang bất kỳ bước tiếp theo nào cho đến khi quá trình review độc lập thật sự được thực hiện lại.

---

## 5. Lệnh Cấm Tuyệt đối Tuyên bố "READY FOR OWNER REVIEW" khi Chưa Đạt Chuẩn (Strict Prohibition)

### Điều khoản Chống Gian lận Nghiêm ngặt:
> **TUYỆT ĐỐI NGHIÊM CẤM** bất kỳ Agent, Worker, hay Coordinator nào đưa ra kết luận hoặc sử dụng nhãn **`READY FOR OWNER REVIEW`** hoặc khuyến nghị **`MERGE`** khi Review Gate chưa đạt trạng thái **`REVIEW_APPROVED`** (hoặc chưa có giải trình kèm bằng chứng đầy đủ cho trạng thái `REVIEW_BLOCKED_BY_PERMISSION` đã được kiểm toán).

### Quy định Kết luận Trạng thái Báo cáo:
Mọi báo cáo nghiệm thu task hoặc PR chỉ được phép kết thúc bằng chính xác **1 trong 3 trạng thái chuẩn** sau:

1. **`READY FOR OWNER REVIEW`**:
   - CHỈ ĐƯỢC DÙNG KHI: Toàn bộ các bước 1 đến 8 đã hoàn thành xuất sắc; Review Gate là `REVIEW_APPROVED`; Auditor đã xác minh độc lập 100% bằng chứng; không còn bất kỳ bất đồng hay sai lệch dữ liệu nào.
2. **`BLOCKED — NEEDS OWNER DECISION`**:
   - DÙNG KHI: Xuất hiện vướng mắc vượt thẩm quyền của Agent (ví dụ: xung đột kiến trúc cấp cao, hạn chế quyền tài khoản GitHub tác giả PR, cần quyết định phương án đánh đổi kỹ thuật).
3. **`NOT READY — MORE FIXES REQUIRED`**:
   - DÙNG KHI: Còn test fail, phát hiện hồi quy, finding của Reviewer chưa được Worker sửa xong, hoặc thiếu bằng chứng xác thực.

Mọi hành vi vi phạm điều khoản này (ví dụ: tự ý tuyên bố sẵn sàng duyệt khi chưa có code review) sẽ bị Hệ thống Kiểm toán Độc lập (Auditor) đánh dấu là **Integrity Violation** và toàn bộ báo cáo sẽ bị bác bỏ ngay lập tức.

---

## 6. Cơ chế Công bố GitHub Review và Ranh giới Identity (GitHub Review Publication Rules)

Để bảo đảm tính minh bạch và tuân thủ các quy tắc bảo mật của GitHub:

### 6.1. Quy tắc Ranh giới Identity trên GitHub (GitHub Identity Boundary)
- **Ràng buộc nền tảng GitHub:** Theo quy định của GitHub, một người dùng **KHÔNG THỂ tự Approve hoặc Request Changes trên Pull Request do chính mình tạo ra** (API sẽ trả về HTTP 422: `Unprocessable Entity`).
- Do đó, nếu môi trường chạy AI sử dụng chung tài khoản GitHub CLI (`gh`) của Project Owner (ví dụ `nguyenphanminhkhanh9a-netizen`), Agent đóng vai Reviewer **KHÔNG THỂ** giả lập một GitHub Review Approval chính thức thay cho Owner.
- **Phân loại hành động rõ ràng:**
  - Nếu gửi nhận xét qua CLI dưới tài khoản tác giả, hành động đó phải được phân loại chính xác là **Issue Comment** hoặc **Review Comment (Advisory)**; TUYỆT ĐỐI KHÔNG được tuyên bố là "External Independent GitHub Review Approval".
  - Để có GitHub Required Approval tự động thực sự trong CI/CD, dự án cần cấu hình một GitHub App hoặc bot account riêng biệt có quyền thành viên trong tổ chức.

### 6.2. Lệnh GitHub CLI Chuẩn để Đăng Nhận xét / Báo cáo
Khi Review hoàn thành và cần ghi nhận lên PR, sử dụng lệnh:

```powershell
# 1. Đăng nhận xét tổng hợp lên PR dưới dạng Issue Comment
gh pr comment <PR_NUMBER> --body-file "<PATH_TO_REVIEW_MARKDOWN>"

# 2. Hoặc sử dụng lệnh gh pr review ở chế độ comment (không approve)
gh pr review <PR_NUMBER> --comment --body-file "<PATH_TO_REVIEW_MARKDOWN>"
```

### 6.3. Quy trình Đăng Thủ công Dành cho Project Owner (Manual Runbook)
Khi hệ thống ghi nhận trạng thái `REVIEW_BLOCKED_BY_PERMISSION` do ràng buộc tài khoản, Project Owner sẽ thực hiện các bước sau để phê duyệt chính thức trên giao diện web GitHub:

1. Truy cập vào trang Pull Request trên trình duyệt (ví dụ: `https://github.com/nguyenphanminhkhanh9a-netizen/Project-AIC/pull/7`).
2. Mở tab **Files changed**.
3. Đọc báo cáo Code Review độc lập do Agent lập (ví dụ: được lưu tại `docs/reviews/PR_7_INDEPENDENT_CODE_REVIEW.md`).
4. Nhấn nút xanh **Review changes** ở góc trên bên phải.
5. Chọn **Approve** (nếu đồng thuận với kết quả) và paste tóm tắt từ báo cáo vào ô nhận xét.
6. Nhấn **Submit review**.
7. Tiến hành Merge PR khi tất cả các kiểm tra an toàn đã hoàn tất.

---

## 7. Tích hợp Phân vai trong Google Antigravity Teamwork (Role Integration)

Tất cả các Agent khi tham gia vào quy trình phát triển Project AIC phải tuân thủ ma trận phân nhiệm sau:

| Vai trò Agent | Trách nhiệm đối với Code Review Policy | Điều kiện Hoàn thành Nhiệm vụ |
|---|---|---|
| **Project Owner** | Duyệt kiến trúc, ra quyết định khi bị Blocked, thực hiện Approve và Merge thủ công. | N/A (Chủ sở hữu dự án) |
| **Sentinel / Coordinator** | Khởi tạo milestone, thiết lập workspace cô lập, phân định ranh giới giữa Worker và Reviewer. | Đảm bảo Reviewer được giao việc độc lập; không cho phép đóng task khi chưa có review. |
| **Project Orchestrator** | Giám sát luồng 9 bước, điều phối chuyển giao giữa Worker và Reviewer; tổng hợp deliverables. | Tất cả PR phải có trạng thái Review Gate rõ ràng trước khi tổng hợp báo cáo. |
| **Worker / Implementer** | Triển khai mã nguồn, tự kiểm thử (Bước 1 & 2), tiếp thu và sửa đổi findings (Bước 4). | Không tự tuyên bố hoàn thành; phải chờ Reviewer xác nhận đạt ở Bước 6. |
| **Critic / Reviewer** | Soát xét độc lập toàn bộ diff theo 13 nguyên tắc cốt lõi (Bước 3 & 5); ký duyệt (Bước 6). | Phải lập báo cáo review có dẫn chứng dòng code cụ thể, phân loại severity rõ ràng. |
| **Challenger / Tester** | Viết test đối kháng, kiểm tra biên, tìm các kịch bản lỗi mà Worker và Reviewer có thể bỏ sót. | Báo cáo danh sách test đối kháng đã chạy thực tế kèm kết quả pass/fail thật. |
| **Auditor / Forensic** | Kiểm toán bằng chứng, kiểm tra chữ ký SHA-256, xác minh tính trung thực của các bài test và lệnh audit. | Bác bỏ bất kỳ báo cáo nào có dấu hiệu hardcode, dummy, hoặc vi phạm lệnh cấm tại Mục 5. |
| **Owner Liaison / Secretary**| Soạn thảo báo cáo bàn giao, bắt buộc bổ sung mục "TÓM TẮT DỄ HIỂU DÀNH CHO SẾP" theo đúng quy định. | Báo cáo trung thực đúng 1 trong 3 trạng thái kết thúc chuẩn; tuyệt đối không tô hồng dữ liệu. |

---

## 8. Điều khoản Hiệu lực (Enforcement & Audit Invariants)

1. **Hiệu lực thi hành:** Chính sách này có hiệu lực ngay lập tức kể từ ngày ký và áp dụng cho toàn bộ các Task từ Milestone M0 đến khi có văn bản cập nhật chính thức từ Project Owner.
2. **Không ngoại lệ:** Không một cá nhân hay Agent nào được phép tự ý miễn trừ bất kỳ bước nào trong Quy trình 9 bước hoặc bất kỳ nguyên tắc nào trong 13 Nguyên tắc Đánh giá.
3. **Lưu vết và Kiểm toán:** Toàn bộ lịch sử review, findings và bằng chứng khắc phục phải được lưu giữ vĩnh viễn trong kho lưu trữ tài liệu của repository để phục vụ kiểm toán độc lập.
