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
