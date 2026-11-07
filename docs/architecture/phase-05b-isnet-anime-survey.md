# BÁO CÁO KHẢO SÁT KIẾN TRÚC & ĐỀ XUẤT TÍCH HỢP PHASE 0.5B: TÁCH NỀN ANIME BẰNG IS-NET ANIME (ONNX RUNTIME DIRECTML / CPU FALLBACK)

**Dự án:** Project AIC — Autonomous AI Companion (Miku Character Engine)  
**Tài liệu:** Báo cáo Khảo sát Kiến trúc Kỹ thuật Phase 0.5B (Architectural Survey & Integration Proposal)  
**Mã tài liệu:** `docs/architecture/phase-05b-isnet-anime-survey.md`  
**Nhánh triển khai đề xuất:** `docs/m0-task-05b-architecture-survey` (phân nhánh từ `main`)  
**Commit cơ sở:** `fb5b21f0fa59ddc4983d29f1500f5672d3b7205e` (Merge PR #5 — Pipeline Core Phase 0.5A)  
**Commit khảo sát cơ sở trên remote:** `8b92a2b821a4844925640c184ca7570736053151` (Đã đẩy lên remote origin)  
**Commit hiệu đính & kiểm chứng R1 trên remote:** `0f9160c99823ce025738c30c70ca81280020cc8e` (Đã đẩy lên remote origin)  
**Commit kiểm toán đối kháng Cycle 1 Reviewer R1 trên remote:** `f8590bd97b17678aac2c05699b179711a485c06b` (Đã đẩy lên remote origin)  
**Commit kiểm toán đối kháng Cycle 1 Reviewer R2 trên remote:** `7949c0afe55c7c504689fc2e44d00ccf829a709f` (Đã đẩy lên remote origin)  
**Commit kiểm toán đối kháng Cycle 1 Reviewer R3 trên remote:** `5c343418dee88169583d76bdded1792b8dc844d6` (Đã đẩy lên remote origin)  
**Commit hiệu đính Implementer trên remote:** `1ffeb67bd6da24d2155169621d01d35050befdc3` (Đã đẩy lên remote origin)  
**Commit kiểm toán đối kháng Reviewer R1 trên remote:** `8700382693f447d296258e021b8a989f59a22fc6` (Đã đẩy lên remote origin)  
**Tác giả:** worker_05b_2 (Implementer), reviewer_05b_r1 (Reviewer R1) & reviewer_05b_r2 (Reviewer R2)  
**Ngày lập & Cập nhật:** 07/11/2026 (Hiệu đính Đối kháng Hoàn thiện R1–R6 — Round 2)  
**Chế độ tuân thủ:** Integrity Mode Development — Cam kết trung thực tuyệt đối, không gian lận, không giả lập kết quả.

---

## MỤC LỤC CHI TIẾT

1. [TỔNG QUAN KIẾN TRÚC & TÓM TẮT ĐIỀU HÀNH](#1-t%E1%BB%95ng-quan-ki%E1%BA%BFn-tr%C3%BAc-t%C3%B3m-t%E1%BA%AFt-%C4%91i%E1%BB%81u-h%C3%A0nh)
2. [KHẢO SÁT KIẾN TRÚC CƠ SỞ & KIỂM TOÁN HỢP ĐỒNG HIỆN HỮU (Baseline Architecture Audit)](#2-kh%E1%BA%A3o-s%C3%A1t-ki%E1%BA%BFn-tr%C3%BAc-c%C6%A1-s%E1%BB%9F-ki%E1%BB%83m-to%C3%A1n-h%E1%BB%A3p-%C4%91%E1%BB%93ng-hi%E1%BB%87n-h%E1%BB%AFu-baseline-architecture-audit)
   - 2.1 Protocol `BackgroundRemovalProvider` và Hợp đồng Dữ liệu
   - 2.2 Kiểm toán Bộ tách nền Giả lập `MockBackgroundRemovalProvider`
   - 2.3 Luồng Điều phối 10 Giai đoạn của `PipelineWorker`
   - 2.4 Hàng rào Bảo mật Đa tầng `ImageSanitizer` và `SafeDownloader`
   - 2.5 Chuẩn hóa Canvas (`SpriteNormalizer`) và Đo lường Độ lệch (`DriftVerificationEngine`)
   - 2.6 Cổng Kiểm soát Chất lượng Tổng hợp (`CQSQualityGate`) và Lọc Trùng lặp
   - 2.7 Tính Bất biến Lưu trữ Nguyên tử và Cô lập Trạng thái Khách (`READY Invariant`)
   - 2.8 Hiện trạng Bộ Kiểm thử Cơ sở (218/218 Tests Passing - Pipeline Core & Mock)
3. [NGUỒN GỐC MÔ HÌNH, BẢN QUYỀN & XÁC MINH MÃ HÓA (R1 Model Provenance, Licensing & Pinning)](#3-ngu%E1%BB%93n-g%E1%BB%91c-m%C3%B4-h%C3%ACnh-b%E1%BA%A3n-quy%E1%BB%81n-x%C3%A1c-minh-m%C3%A3-h%C3%B3a-r1-model-provenance-licensing-pinning)
   - 3.1 Nguồn gốc Học thuật: IS-Net và Bộ dữ liệu DIS5K (ECCV 2022)
   - 3.2 Tinh chỉnh Chuyên biệt Cho Anime: SkyTNT (`anime-segmentation`)
   - 3.3 Hệ sinh thái và Các Dự án Kế thừa
   - 3.4 Ma trận Kiểm toán Bản quyền Đa tầng, Bằng chứng Tác giả & Phân tích Rủi ro Pháp lý
   - 3.5 Chiến lược Kiến trúc "Bring-Your-Own-Model" (BYOM) & Giới Hạn Pháp Lý
   - 3.6 Ghim Phiên bản Ổn định Hugging Face, Thông số Kỹ thuật & Dấu vân tay Mật mã SHA-256
   - 3.7 Thuật toán Xác minh Băm SHA-256 Dạng Luồng và Cơ chế Cách ly Sự cố
   - 3.8 Quy định Tuyệt đối: Cấm Tự động Tải Mô hình khi Khởi động hoặc Import
4. [CHẤT LƯỢNG HÌNH ẢNH ANIME & KIẾN TRÚC MẶT NẠ ALPHA (Quality & Alpha Matting)](#4-ch%E1%BA%A5t-l%C6%B0%E1%BB%A3ng-h%C3%ACnh-%E1%BA%A3nh-anime-ki%E1%BA%BFn-tr%C3%BAc-m%E1%BA%B7t-n%E1%BA%A1-alpha-quality-alpha-matting)
   - 4.1 Phân tích 6 Trường hợp Biên (Edge Cases) Đặc thù Của Tranh Anime
   - 4.2 Thiết kế Tiền xử lý: Phép thử Bảo toàn Hình học (Geometry Preservation Test) vs. Chất lượng Phân vùng AI
   - 4.3 Thiết kế Hậu xử lý: Mặt nạ Alpha Mềm (Soft Alpha) và Khôi phục Tọa độ Gốc
   - 4.4 Bộ lọc Tinh chỉnh Cạnh Biên Tùy chọn (Guided Filter)
   - 4.5 Khởi tạo Luồng Byte RGBA Đích Thực (4 Kênh Chuẩn PNG)
   - 4.6 4 Cổng Kiểm chuẩn Đầu ra: Cơ sở Lý thuyết, Điều kiện Loại bỏ Nhầm & Phương pháp Hiệu chuẩn
   - 4.7 Kế hoạch Benchmark Chất lượng Phân vùng AI & Giới hạn của Các Chỉ số Định lượng
   - 4.8 BẢNG PHÂN ĐỊNH BẮT BUỘC: Sự thật Thực nghiệm vs. Giả thuyết Thiết kế
5. [DỰ PHÒNG THIẾT BỊ, QUẢN TRỊ TÀI NGUYÊN & ĐỒNG THỜI (R2 GPU Fallback & R3 Benchmark Plan)](#5-d%E1%BB%B1-ph%C3%B2ng-thi%E1%BA%BFt-b%E1%BB%8B-qu%E1%BA%A3n-tr%E1%BB%8B-t%C3%A0i-nguy%C3%AAn-%C4%91%E1%BB%93ng-th%E1%BB%9Di-r2-gpu-fallback-r3-benchmark-plan)
   - 5.1 Chiến lược Phân tầng Thiết bị Thực thi (DirectML trên DirectX 12 -> CPU)
   - 5.2 Ràng buộc Cấu hình Bắt buộc Của DirectML (`enable_mem_pattern = False`)
   - 5.3 Cô lập Lỗi Khởi tạo GPU Hai Giai đoạn (Hai tầng Try-Catch Phục hồi)
   - 5.4 Ghi log Thiết bị Hoạt động và Metadata Chẩn đoán
   - 5.5 Phân loại Số liệu Hiệu năng (Nhóm A / B / C) & Kế hoạch Benchmark DirectML trên RTX 4050 6GB
   - 5.6 Vòng đời Phiên Thực thi, Khởi tạo Lười (Lazy Loading) và Kiểm soát Đồng thời
   - 5.7 Đề Xuất Thiết Kế Cơ Chế Phục Hồi khi Tràn Bộ Nhớ Đồ Họa (Proposed GPU OOM to CPU Fallback - Chưa Triển Khai)
   - 5.8 Bảo tồn Tính Trừu tượng và Nhà cung cấp Giả lập Cho Môi trường CI
6. [KẾ HOẠCH KIỂM THỬ ĐA TẦNG & CỔNG CHẤT LƯỢNG (R4 Multi-Tier Test Plan & Quality Gate)](#6-k%E1%BA%BF-ho%E1%BA%A1ch-ki%E1%BB%83m-th%E1%BB%AD-%C4%91a-t%E1%BA%A7ng-c%E1%BB%95ng-ch%E1%BA%A5t-l%C6%B0%E1%BB%A3ng-r4-multi-tier-test-plan-quality-gate)
   - 6.1 Tầng 1: Kiểm thử Đơn vị với Mock Provider (Đã Chạy & Vượt Qua - RUN)
   - 6.2 Tầng 2: Kiểm thử Tích hợp CPU ONNX với Mô hình Nhân tạo 2KB (Chưa Chạy - NOT RUN)
   - 6.3 Tầng 3: Kiểm thử Tích hợp Mô hình Thực IS-Net trên CPU (Chưa Chạy - NOT RUN)
   - 6.4 Tầng 4: Kiểm thử Phần cứng DirectML GPU trên Windows (Chưa Chạy - NOT RUN)
7. [RỦI RO KỸ THUẬT, CÁC CHẾ ĐỘ THẤT BẠI & BIỆN PHÁP GIẢM THIỂU](#7-r%E1%BB%A7i-ro-k%E1%BB%B9-thu%E1%BA%ADt-c%C3%A1c-ch%E1%BA%BF-%C4%91%E1%BB%99-th%E1%BA%A5t-b%E1%BA%A1i-bi%E1%BB%87n-ph%C3%A1p-gi%E1%BA%A3m-thi%E1%BB%83u)
8. [DANH MỤC TỆP DỰ KIẾN, LỘ TRÌNH TRIỂN KHAI & XÁC MINH GIT REMOTE (R6 Git & Scope Restrictions)](#8-danh-m%E1%BB%A5c-t%E1%BB%87p-d%E1%BB%B1-ki%E1%BA%BFn-l%E1%BB%99-tr%C3%ACnh-tri%E1%BB%83n-khai-x%C3%A1c-minh-git-remote-r6-git-scope-restrictions)
   - 8.1 Danh mục Tệp Dự kiến
   - 8.2 Lộ trình Triển khai Đề xuất
   - 8.3 Xác minh Git Remote & Khẳng định Giới hạn Phạm vi (R6 Git & Scope Restrictions)
9. [TÓM TẮT DỄ HIỂU DÀNH CHO SẾP (R5 Plain Language Summary for Owner)](#9-t%C3%B3m-t%E1%BA%AFt-d%E1%BB%85-hi%E1%BB%83u-d%C3%A0nh-cho-s%E1%BA%BFp-r5-plain-language-summary-for-owner)

---

## 1. TỔNG QUAN KIẾN TRÚC & TÓM TẮT ĐIỀU HÀNH

Mục tiêu kỹ thuật cốt lõi của **Phase 0.5B** là nâng cấp hệ thống xử lý sprite nhân vật Hatsune Miku từ việc sử dụng thuật toán giả lập cắt nền heuristic (`MockBackgroundRemovalProvider`) sang mô hình AI chuyên dụng tách nền anime hiện đại: **IS-Net Anime** (Dichotomous Image Segmentation fine-tuned for Anime), vận hành thông qua runtime mở rộng phần cứng **ONNX Runtime với DirectML** trên hệ điều hành Windows (tương thích các dòng card đồ họa NVIDIA, AMD, Intel qua DirectX 12) và đề xuất thiết kế cơ chế dự phòng tự động chuyển sang **CPUExecutionProvider** khi máy tính không có GPU chuyên dụng hoặc gặp sự cố khởi tạo runtime (thiết kế kiến trúc đề xuất cho Phase 0.5B, chưa được triển khai hay kiểm thử trong codebase hiện tại).

### Sơ đồ Khái niệm Luồng Xử lý Toàn tuyến (End-to-End Pipeline Overview)

```
[Nguồn Ảnh Tải Về / Cache]
          │ (bytes)
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. HÀNG RÀO BẢO MẬT & TIỀN KIỂM SOÁT (Security & Ingestion)                  │
│    - SafeDownloader: Chặn SSRF, DNS Rebinding, ghim IP kết nối               │
│    - ImageSanitizer: Kiểm tra header trước giải nén pixel, chặn Bom nén     │
│    - CQSQualityGate (Pre-CQS): Đánh giá độ sắc nét, tương phản sơ khởi      │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │ raw_bytes
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. BỘ TÁCH NỀN AI ĐA CHẾ ĐỘ (Pluggable Background Removal Engine)            │
│    - Factory: Tuyển chọn Provider theo cấu hình (Mock hoặc ONNX)             │
│                                                                             │
│    ┌───────────────────────────────────────────────────────────────────┐    │
│    │ ONNXBackgroundRemovalProvider (IS-Net Anime - 176 MB)             │    │
│    │ - Lazy Loading + Singleton Session (asyncio.Lock bảo vệ)          │    │
│    │ - Tiền xử lý: Letterbox đối xứng -> Canvas 1024x1024              │    │
│    │ - Hardware Fallback (Đề xuất): DirectML ──(lỗi)──► CPU (OpenMP)   │    │
│    │ - Hậu xử lý: Sigmoid -> Cắt biên -> Unpad về (W, H) gốc           │    │
│    │ - Soft Alpha Ramp: [0.05, 0.95] làm mịn viền tóc và vải mỏng      │    │
│    │ - Cổng kiểm chuẩn mặt nạ: Chặn mặt nạ rỗng / đen / trắng hoàn toàn│    │
│    └───────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │ rgba_png_bytes + _bg_meta
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. HẬU XỬ LÝ HÌNH HỌC & KIỂM ĐỊNH TỌA ĐỘ (Geometry & Anchoring)             │
│    - ImageSanitizer: Tái kiểm tra tính toàn vẹn của PNG RGBA đầu ra         │
│    - SpriteNormalizer: Bóc tách BBox Alpha -> Đặt lên Canvas 1024x1536      │
│      (Phân loại neo chân BOTTOM_CENTER, ngang eo WAIST, chân dung EYE)      │
│    - DriftVerificationEngine: Đo độ lệch tâm đầu X & mắt Y đối chiếu Miku   │
│      (<=35px: Duyệt; 35-50px: Bù trừ tọa độ; >50px: Cách ly needs_review)   │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │ normalized_sprite (1024x1536 RGBA)
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. HẬU KIỂM ĐỊNH CHẤT LƯỢNG & LỌC TRÙNG LẶP (Quality Gate & Dedup)          │
│    - CQSQualityGate (Post-CQS): Đánh giá độ phủ silhouette [0.20, 0.85]     │
│    - MultiScaleDeduplicator: Lọc 3 tầng (pHash thô -> Crop mặt -> SSIM)    │
│      (Chấp nhận biểu cảm mới, chặn trùng lặp, cách ly các trường hợp nghi vấn)│
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 5. LƯU TRỮ NGUYÊN TỬ & BẢO ĐẢM TRẠNG THÁI (Storage & Invariants)            │
│    - ManifestManager: Ghi đĩa nguyên tử (.tmp -> fsync -> os.replace)       │
│    - CharacterAssetResolver: Thực thi bất biến READY Invariant               │
│      (Chỉ asset "ready" mới được hiển thị cho Client/Frontend)              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Các Cam kết Kiến trúc Quyết định:
1. **Tuân thủ Tuyệt đối Hợp đồng Hiện hữu:** Giữ nguyên vẹn Protocol `BackgroundRemovalProvider` và lớp `MockBackgroundRemovalProvider`. Bộ kiểm thử CI và môi trường phát triển ngoại tuyến tiếp tục chạy 100% không phụ thuộc mô hình nặng hay GPU.
2. **Bảo mật Chuỗi cung ứng (Supply Chain Security):** Áp dụng kiến trúc **BYOM (Bring-Your-Own-Model)**. Không đóng gói kèm file nhị phân mô hình trong kho mã nguồn Git. Mô hình chỉ được nạp sau khi vượt qua thuật toán kiểm tra mã băm mật mã **SHA-256 dạng luồng (streaming)** trước khi chuyển cho runtime ONNX. Tuyệt đối nghiêm cấm việc tự ý tải mô hình từ mạng khi `import` module hoặc khi ứng dụng khởi động.
3. **Định Hướng Chất Lượng Tách Viền Anime & Mục Tiêu Thiết Kế:** Đề xuất kỹ thuật đệm khung (letterboxing) giữ nguyên tỷ lệ khung hình thực, không kéo giãn làm biến dạng giải phẫu nhân vật Miku; thiết kế dải alpha mềm liên tục $A \in [0.05, 0.95]$ với mục tiêu tối ưu khả năng bảo tồn chi tiết sợi tóc mai (ahoge), phụ kiện nơ bay, vòng hào quang tóc (angel rings) và khăn voan bán trong suốt (chất lượng phân vùng thực tế sẽ được kiểm chứng thực nghiệm bằng tập benchmark ở Phase 0.5B); tích hợp 4 cổng kiểm soát chất lượng mặt nạ đầu ra nhằm phát hiện và lọc bỏ các trường hợp ảnh đen/trắng bất thường.
4. **Đề Xuất Thiết Kế Dự Phòng Phần Cứng (Proposed Fallback Design):** Đề xuất thiết kế cô lập lỗi khởi tạo DirectML bằng khối try-catch hai giai đoạn (khởi tạo phiên và suy luận khởi động `warmup`). Khi phát hiện sự cố thiếu tính năng phần cứng hoặc lỗi DirectML có thể bắt được, hệ thống đề xuất chuyển sang CPU đa luồng. *Lưu ý phân định quan trọng:* Cơ chế này hiện là **đề xuất thiết kế kiến trúc cho Phase 0.5B, CHƯA ĐƯỢC TRIỂN KHAI hay kiểm chứng trong codebase hiện tại**; không bảo đảm mọi lỗi driver DirectX 12 hoặc tràn bộ nhớ VRAM đều có thể khôi phục an toàn (các lỗi phần cứng nghiêm trọng, TDR reset hoặc cạn kiệt RAM hệ thống vẫn có thể làm dừng worker).

---

## 2. KHẢO SÁT KIẾN TRÚC CƠ SỞ & KIỂM TOÁN HỢP ĐỒNG HIỆN HỮU (Baseline Architecture Audit)

Khảo sát được thực hiện trực tiếp trên nhánh `main` tại commit `fb5b21f0fa59ddc4983d29f1500f5672d3b7205e` (sau khi hoàn tất tích hợp PR #5 của Task 0.5A).

### 2.1 Protocol `BackgroundRemovalProvider` và Hợp đồng Dữ liệu
Giao diện cốt lõi cho các nhà cung cấp dịch vụ tách nền được định nghĩa tại `backend/app/domain/pipeline.py` (dòng 78–103) như sau:

```python
@runtime_checkable
class BackgroundRemovalProvider(Protocol):
  """Protocol for background removal providers (Mock in 0.5A, ONNX in 0.5B)."""

  @property
  def model_name(self) -> str:
    """Name of the background matting model or provider."""
    ...

  @property
  def execution_provider(self) -> str:
    """Execution backend ('cpu_mock', 'directml', 'cpu')."""
    ...

  async def remove_background(
      self,
      image_bytes: bytes,
      **kwargs: Any,
  ) -> tuple[bytes, dict[str, Any]]:
    """Processes RGB image bytes and returns (transparent_png_bytes, metadata_dict)."""
    ...

  def release(self) -> None:
    """Explicitly releases cached sessions, models, and OS memory."""
    ...
```

#### Bảng Kiểm toán Hợp đồng Trao đổi:
| Thành phần Hợp đồng | Kiểu Dữ liệu Thực tế | Ràng buộc Kỹ thuật & Kỳ vọng |
|---|---|---|
| **Đầu vào Ảnh** | `bytes` (`image_bytes`) | Luồng byte nhị phân của ảnh gốc (JPEG, PNG, WebP), đã được giải mã và kiểm tra kích thước an toàn qua `SafeDownloader` và `ImageSanitizer`. |
| **Tham số Mở rộng** | `**kwargs: Any` | Cho phép truyền các cờ điều khiển suy luận linh hoạt (ngưỡng nhạy, thiết bị ưu tiên, cờ bỏ qua hậu lọc). |
| **Đầu ra Ảnh** | `bytes` (phần tử thứ 1 của tuple) | Luồng byte định dạng PNG 4 kênh chuẩn `RGBA`, bảo đảm giá trị cực trị của kênh Alpha đạt `(0, 255)`. |
| **Metadata Trả về** | `dict[str, Any]` (phần tử thứ 2 của tuple) | Từ điển chứa siêu dữ liệu đo kiểm: `model_name`, `execution_provider`, `latency_ms`, `alpha_source`, `alpha_extrema`. |
| **Giải phóng Tài nguyên**| `def release(self) -> None` | Hàm đồng bộ giải phóng tài nguyên phiên ONNX, xóa bộ đệm tensor đồ họa, dọn dẹp RAM qua `gc.collect()`. |

*Lưu ý về thuật ngữ DTO*: Trong mã nguồn thực tế của Task 0.5A, quy trình chuyển giao dữ liệu tầng xử lý ảnh trực tiếp trao đổi dạng `bytes` nguyên thủy và trả về `tuple[bytes, dict[str, Any]]`, trong khi các thực thể điều phối vòng đời cấp cao sử dụng `PipelineTask` (`backend/app/domain/pipeline.py:163-181`) và `PipelineResult` (`backend/app/domain/pipeline.py:183-194`). Không có lớp nào mang tên `ImageProcessingRequest` hay `ImageProcessingResult`.

### 2.2 Kiểm toán Bộ tách nền Giả lập `MockBackgroundRemovalProvider`
Tệp tin: `backend/app/pipeline/background/mock_provider.py` (dòng 1–142).
- Hoạt động 100% trong bộ nhớ (in-memory) bằng Pillow và NumPy, không yêu cầu GPU hay bất kỳ thư viện học máy nào.
- Thuật toán xử lý:
  1. **Bảo toàn Alpha sẵn có:** Nếu ảnh đầu vào đã có kênh Alpha với cực trị `(0, 255)`, giữ nguyên và đóng gói lại (`alpha_source="preserved_existing_alpha"`).
  2. **Lấy mẫu 4 góc (Corner Sampling):** Lấy mẫu mảng 5x5 pixel tại 4 góc của ảnh RGB, tính màu nền trung vị $C_{\text{bg}} = \text{median}(\text{corners})$.
  3. **Khoảng cách Màu Euclid & Làm mờ biên (Feathering):** Tính khoảng cách $D = \sqrt{\sum (C - C_{\text{bg}})^2}$. Khoảng cách $< 18$ gán $\alpha=0$; $> 48$ gán $\alpha=255$; ở giữa nội suy tuyến tính.
  4. **Dự phòng Silhouette Nhân tạo:** Nếu nền ảnh phức tạp hoặc có hoa văn (độ che phủ nhân vật rơi ra ngoài khoảng $[0.10, 0.90]$), tự động vẽ bóng nhân vật hình elip (đầu) và đa giác (thân) để bảo đảm kênh alpha có độ che phủ hợp lệ.
  5. **Bảo đảm Cực trị Tuyệt đối:** Luôn thực thi lệnh kiểm tra nghiêm ngặt `assert final_alpha.getextrema() == (0, 255)`.

### 2.3 Luồng Điều phối 10 Giai đoạn của `PipelineWorker`
Tệp tin: `backend/app/pipeline/worker.py` (dòng 37–285).
Tiến trình xử lý một tác vụ nhân vật (`process_task`) đi qua chuỗi 10 giai đoạn tuần tự:
```
[1. download]      -> Tải dữ liệu an toàn qua SafeDownloader
[2. sanitize]      -> Tiền kiểm định và khử độc qua ImageSanitizer
[3. quality_pre]   -> Đánh giá chất lượng thô qua CQSQualityGate (Rớt -> rejected)
[4. bg_removal]    -> Gọi bg_provider.remove_background(raw_bytes)
                      và tái kiểm định bg_cutout = sanitizer.sanitize_image(rgba_bytes)
[5. alignment]     -> Đặt nhân vật lên canvas 1024x1536 qua SpriteNormalizer
[6. drift_check]   -> Đo sai lệch giải phẫu mắt/đầu qua DriftVerificationEngine
[7. quality_post]  -> Hậu kiểm tra độ sắc nét, tương phản, độ phủ silhouette
[8. dedup]         -> Kiểm tra trùng lặp 3 tầng qua MultiScaleDeduplicator
[9. status_eval]   -> Tổng hợp trạng thái: Có nghi vấn -> "needs_review", đạt -> "ready"
[10. storage/commit]-> Ghi ảnh WebP và cập nhật manifest.json nguyên tử
```
*Phát hiện quan trọng cho Task 0.5B*: Tại dòng 166 của `worker.py`, biến `_bg_meta` hiện đang được nhận về dưới dạng biến cục bộ nhưng chưa được ghi vào `task.metadata`. Trong giai đoạn triển khai 0.5B, metadata chẩn đoán của mô hình ONNX (`execution_provider`, `latency_ms`) cần được gắn vào bản ghi kết quả của tác vụ.

### 2.4 Hàng rào Bảo mật Đa tầng `ImageSanitizer` và `SafeDownloader`
- **`ImageSanitizer`** (`backend/app/pipeline/security/sanitizer.py`):
  - Kiểm tra chữ ký magic bytes nhị phân thực của file (PNG: `\x89PNG\r\n\x1a\n`, JPEG: `\xff\xd8\xff`, WebP: `RIFF....WEBP`).
  - Kiểm soát độ phân giải trước khi giải mã raster (Pre-rasterization pixel check): đọc header qua `Image.open()`, kiểm tra `width * height <= self.max_pixels` ngay lập tức, ngăn chặn hoàn toàn các cuộc tấn công từ chối dịch vụ dạng bom giải nén (Decompression Bomb 100MP, 225MP) mà không cấp phát bộ nhớ RAM khổng lồ.
  - **Loại bỏ hoàn toàn biến đổi trạng thái toàn cục:** Sau kiểm toán của PR #5, lớp này hoàn toàn không thay đổi `Image.MAX_IMAGE_PIXELS` toàn cục và không can thiệp vào bộ lọc cảnh báo `warnings.filters`, bảo đảm an toàn luồng tuyệt đối khi chạy đa luồng đồng thời.
  - Tái tạo ảnh trên canvas RGBA trắng tinh để gọt sạch toàn bộ metadata nguy hiểm (EXIF, XMP, ICC profile, bình luận nhúng mã độc polyglot).
- **`SafeDownloader`** (`backend/app/pipeline/security/safe_downloader.py`):
  - Sử dụng backend mạng tùy biến `SSRFSafeNetworkBackend` chặn đứng tấn công SSRF và DNS Rebinding bằng cách ghim địa chỉ IP đã xác thực trực tiếp vào kết nối TCP.
  - Giới hạn tải luồng streaming tối đa 15 MB, bộ nhớ đệm kép giới hạn 64 mục và 64 MB tổng dung lượng.

### 2.5 Chuẩn hóa Canvas (`SpriteNormalizer`) và Đo lường Độ lệch (`DriftVerificationEngine`)
- **`SpriteNormalizer`** (`backend/app/pipeline/processing/normalizer.py`):
  - Quy chuẩn kích thước canvas cố định: **1024 x 1536 pixels RGBA**.
  - Phân loại cạnh tiếp giáp đáy thông minh (`classify_edge`): dựa trên tọa độ hộp bao `alpha.getbbox() -> (x1, y1, x2, y2)`. Nếu nhân vật chạm đáy canvas trong phạm vi 5%, phân biệt giữa chân dung cận cảnh (`EYE_LEVEL`) và bán thân (`WAIST_LEVEL`). Nếu không chạm đáy, phân loại thành toàn thân đứng (`BOTTOM_CENTER`).
  - Đặt neo chân toàn thân tại tọa độ đáy $Y=1511$ (chừa lề 25px phía dưới), bảo đảm nhân vật đứng vững chắc trên sàn màn hình.
- **`DriftVerificationEngine`** (`backend/app/pipeline/processing/drift_analyzer.py`):
  - Trích xuất tâm đầu $X$ (tính trung bình hoành độ của 20% silhouette trên cùng) và đường mắt $Y$ ($Y_1 + 0.228 \times H_{\text{sil}}$).
  - So sánh độ lệch với ảnh gốc chuẩn Miku (`miku_core_idle_neutral`):
    - Độ lệch $\le 35\text{px}$: Hợp lệ, không cần can thiệp.
    - $35\text{px} < \text{Độ lệch} \le 50\text{px}$: Tự động bù trừ tọa độ hiển thị (viewport offset compensation).
    - Độ lệch $> 50\text{px}$: Lệch giải phẫu nghiêm trọng $\rightarrow$ Đưa vào trạng thái cách ly `needs_review`.

### 2.6 Cổng Kiểm soát Chất lượng Tổng hợp (`CQSQualityGate`) và Lọc Trùng lặp
- **Chỉ số CQS (Composite Quality Score)**:
  $$\text{CQS} = 0.35 \times S_{\text{sharp}} + 0.25 \times S_{\text{contrast}} + 0.25 \times S_{\text{coverage}} + 0.15 \times S_{\text{res}}$$
  - Sàn độ phân giải tối thiểu: Từ chối ngay nếu chiều rộng $< 512$ hoặc chiều cao $< 768$.
  - Ngưỡng quyết định: $\text{CQS} \ge 0.65$ là Đạt (`ready`); $0.50 \le \text{CQS} < 0.65$ là Cách ly (`needs_review`); $\text{CQS} < 0.50$ là Từ chối (`rejected`).
- **Lọc trùng lặp 3 tầng (`MultiScaleDeduplicator`)**:
  - Tầng 1: pHash toàn cục 64-bit (khoảng cách Hamming $> 16$ chấp nhận ngay là tư thế khác).
  - Tầng 2: pHash và độ tương đồng cấu trúc SSIM của vùng khuôn mặt (25% trên cùng của BBox).
  - Ma trận quyết định: SSIM $\ge 0.94$ và khoảng cách mặt $\le 2 \rightarrow$ Trùng lặp (`reject`); SSIM $< 0.88$ và khoảng cách $\ge 8 \rightarrow$ Biểu cảm mới độc đáo (`accept`); vùng lấp lửng ở giữa đưa vào cách ly (`needs_review`).

### 2.7 Tính Bất biến Lưu trữ Nguyên tử và Cô lập Trạng thái Khách (`READY Invariant`)
- **Ghi đĩa Nguyên tử (`ManifestManager`)**: Mọi thao tác ghi danh mục `manifest.json` đều thực hiện qua tệp tạm `.tmp`, gọi lệnh đẩy bộ đệm người dùng `flush()`, ép xung ghi đĩa phần cứng `os.fsync()`, và hoán đổi con trỏ file nguyên tử bằng `os.replace()`. Nếu tiến trình gặp sự cố giữa chừng, tệp ảnh mới tạo sẽ được thu hồi (unlink rollback), loại bỏ hoàn toàn nguy cơ rác file mồ côi.
- **Bất biến READY Invariant (`CharacterAssetResolver`)**:
  - Hàm `_build_index()` **chỉ lập chỉ mục cho các asset có `status == "ready"`**.
  - Kể cả tại nhánh dự phòng mặc định cuối cùng (Level 5 `default_fallback`), nếu asset được chọn không ở trạng thái `ready`, hệ thống lập tức ném ngoại lệ `DefaultAssetNotReadyError`.
  - Các tài sản ở trạng thái `needs_review`, `pending`, `processing`, `failed`, hoặc `rejected` tuyệt đối không bao giờ bị lộ ra giao diện người dùng.

### 2.8 Hiện trạng Bộ Kiểm thử Cơ sở (218/218 Tests Passing - Pipeline Core & Mock)
Hệ thống hiện sở hữu **218 bài kiểm thử tự động**, chia thành:
- 149 bài kiểm thử chuyên sâu cho toàn bộ pipeline (`backend/tests/pipeline/`).
- 15 bài kiểm thử bất biến cho bộ phân giải tài nguyên nhân vật (`backend/tests/domain/`).
- 54 bài kiểm thử nền tảng và kho lưu trữ SQLite/JSON (`backend/tests/`).
- Kết quả kiểm chứng thực tế tại thời điểm khảo sát:
  - `pytest`: **218 passed** trong 37.04 giây (100% offline, không có lỗi).
  - `ruff check .`: **All checks passed** (0 cảnh báo linting).
  - `mypy app tests`: **Success: no issues found in 72 source files** (Kiểm tra kiểu tĩnh nghiêm ngặt).

> **CẢNH BÁO PHÂN ĐỊNH PHẠM VI KIỂM THỬ (TEST SCOPE BOUNDARY):**  
> Kết quả 218/218 bài kiểm thử vượt qua này **thuần túy là kiểm thử cho bộ khung Pipeline Core (Task 0.5A) sử dụng bộ tách nền giả lập `MockBackgroundRemovalProvider`**.  
> Kết quả này **TUYỆT ĐỐI KHÔNG CHỨNG MINH RẰNG MÔ HÌNH AI IS-NET THỰC TẾ HAY PROVIDER DIRECTML ĐÃ HOẠT ĐỘNG** trong hệ thống. Mô hình thực tế và runtime DirectML chưa được tích hợp mã nguồn hay chạy kiểm thử trong codebase hiện tại.

---

## 3. NGUỒN GỐC MÔ HÌNH, BẢN QUYỀN & XÁC MINH MÃ HÓA (R1 Model Provenance, Licensing & Pinning)

### 3.1 Nguồn gốc Học thuật: IS-Net và Bộ dữ liệu DIS5K (ECCV 2022)
Kiến trúc cốt lõi của mô hình IS-Net xuất phát từ công trình nghiên cứu thị giác máy tính đỉnh cao:
- **Tên bài báo:** *"Highly Accurate Dichotomous Image Segmentation"* (Báo cáo tại Hội nghị ECCV 2022).
- **Nhóm tác giả:** Xuebin Qin, Hang Dai, Xiaobin Hu, Deng-Ping Fan, Ling Shao, Luc Van Gool.
- **Cơ quan nghiên cứu:** Inception Institute of Artificial Intelligence (IIAI), ETH Zürich, MBZUAI, Computer Vision Lab.
- **Kho lưu trữ chính thức:** [`https://github.com/xuebinqin/DIS`](https://github.com/xuebinqin/DIS) (Mã nguồn được cấp phép theo Apache License 2.0).
- **Đặc trưng kiến trúc:** Khác với các mạng phân vùng ảnh truyền thống (như U-2-Net hay MODNet chỉ nhận ảnh $320 \times 320$ hoặc $512 \times 512$ dẫn tới mất chi tiết sợi tóc), IS-Net được thiết kế đặc thù cho **phân vùng nhị phân độ chính xác siêu cao** ở độ phân giải gốc $1024 \times 1024$. Mạng sử dụng các khối ReSidual U-blocks (RSU) kết hợp cơ chế giám sát trung gian (Intermediate Supervision) ở cả cấp độ mặt nạ (`IS-Net_M`) và cấp độ đặc trưng (`IS-Net_F`), duy trì độ phân giải không gian cao xuyên suốt các tầng tích chập sâu.

### 3.2 Tinh chỉnh Chuyên biệt Cho Anime: SkyTNT (`anime-segmentation`)
Mặc dù IS-Net bản gốc hoạt động xuất sắc trên ảnh chụp đời thực, nó gặp nhiều nhược điểm khi áp dụng vào tranh minh họa anime 2D: nét mực viền (line art) bị nhầm là viền vật thể cần cắt gọt, các mảng màu đổ bóng kiểu cel-shading bị nhận diện sai thành bóng đổ ngoại cảnh, và sợi tóc mai mảnh (ahoge) thường bị đứt đoạn.

Để giải quyết bài toán này, tác giả mã nguồn mở **SkyTNT** đã thực hiện tinh chỉnh chuyên sâu (fine-tuning) kiến trúc `isnet_is`:
- **Tác giả chính:** SkyTNT.
- **Kho mã nguồn GitHub:** [`https://github.com/SkyTNT/anime-segmentation`](https://github.com/SkyTNT/anime-segmentation) (Apache License 2.0).
- **Kho mô hình Hugging Face:** [`https://huggingface.co/skytnt/anime-seg`](https://huggingface.co/skytnt/anime-seg) (Model card xác nhận Apache-2.0).
- **Tập dữ liệu huấn luyện:** Hàng chục ngàn nhân vật anime được bóc tách chuẩn xác và ghép nối trên các bối cảnh nhân tạo ngẫu nhiên, huấn luyện mạng học cách tách nét viền mực đen, giữ lại các hiệu ứng gradient tóc bóng mượt và các chi tiết trang phục ren/voan phức tạp.

### 3.3 Hệ sinh thái và Các Dự án Kế thừa
Trọng số mô hình `isnetis.onnx` của SkyTNT hiện đã trở thành chuẩn mực công nghiệp thực tế (de facto standard) cho tác vụ bóc nền anime và được tích hợp rộng rãi:
- **`danielgatis/rembg`**: Thư viện tách nền phổ biến nhất thế giới trên Python (gói mô hình dưới tên `"isnet-anime"`).
- **`Sanster/IOPaint` (tiền thân là lama-cleaner)**: Công cụ inpainting hàng đầu sử dụng trọng số này để cô lập nhân vật hoạt hình.
- **ComfyUI & Stable Diffusion WebUI**: Các node xử lý ảnh anime tự động (`comfyui_animeseg`, `rembg-anime`).

### 3.4 Ma trận Kiểm toán Bản quyền Đa tầng, Bằng chứng Tác giả & Phân tích Rủi ro Pháp lý

Để bảo đảm tính minh bạch pháp lý cho Project AIC, hệ thống phân định rạch ròi 3 tầng bản quyền độc lập: **Mã nguồn (Source Code)**, **Trọng số mô hình (Model Weights)**, và **Tập dữ liệu huấn luyện (Training Dataset)**:

| Tầng (Layer) | Thành phần Cụ thể | Giấy phép Khai báo | Nguồn Chứng thực Khách quan | Đánh giá Khả năng Sử dụng Thương mại |
|---|---|---|---|---|
| **Mã nguồn (Code)** | `xuebinqin/DIS` (IS-Net gốc) | **Apache-2.0** | Tệp `LICENSE` trong repo GitHub gốc | **HỢP LỆ** (Tự do thương mại, sửa đổi, phân phối có kèm ghi nhận tác giả) |
| **Mã nguồn (Code)** | `SkyTNT/anime-segmentation` | **Apache-2.0** | Tệp `LICENSE` trong repo GitHub SkyTNT | **HỢP LỆ** (Mã nguồn mở chuẩn Apache 2.0 cấp phép rộng rãi) |
| **Mã nguồn (Code)** | `danielgatis/rembg` | **MIT** | Tệp `LICENSE.txt` trong repo danielgatis/rembg | **HỢP LỆ** (Giấy phép MIT tiêu chuẩn thương mại) |
| **Trọng số (Weights)** | `skytnt/anime-seg` (`isnetis.onnx`) | **Apache-2.0** | Commit `493cb60893f47441b26ec4fb9a306bce9e342982` trên Hugging Face | **HỢP LỆ** (Chính tác giả SkyTNT xác nhận và cấp phép Apache-2.0) |
| **Tập dữ liệu (Dataset)**| SkyTNT Anime Dataset | **CC0-1.0 Universal** | Thẻ Dataset Card trên Hugging Face | **HỢP LỆ** (Hiến tặng phạm vi công cộng Public Domain) |
| **Tập dữ liệu (Dataset)**| DIS5K (`xuebinqin/DIS`) | **Phi thương mại tùy biến (NC)**| `DIS5K-Dataset-Terms-of-Use.pdf` | **CHỈ HỌC THUẬT** (Ràng buộc phi thương mại đối với tệp dữ liệu gốc) |
| **Tập dữ liệu (Dataset)**| Tranh anime gốc trên internet | **Bản quyền tác giả gốc** | Web scraping Danbooru/Pixiv | **Cần đánh giá pháp lý theo tài phán** (Có thể lập luận theo Fair Use Hoa Kỳ §107 hoặc Điều 30-4 Luật Bản quyền Nhật Bản nhưng chưa đồng nhất giữa các quốc gia và còn tranh chấp) |

#### Bằng chứng Khách quan Về Giấy phép Apache-2.0 Của Trọng số Mô hình:
Quá trình kiểm toán kho lưu trữ Hugging Face chính thức [`skytnt/anime-seg`](https://huggingface.co/skytnt/anime-seg) đã ghi nhận bằng chứng cam kết pháp lý tường minh từ chính tác giả:
1. **Commit Xác nhận Bản quyền:** Vào ngày 17/08/2026 (theo dấu thời gian Hugging Face UTC: `2026-08-17T07:09:17.000Z`), tác giả `skytnt` đã chủ động thực hiện commit có mã hash `493cb60893f47441b26ec4fb9a306bce9e342982` với tiêu đề chính thức: `"update license"`.
2. **Metadata YAML Frontmatter:** Tệp `README.md` của repo được cập nhật thẻ chuẩn `license: apache-2.0`.
3. **Model Card Tags:** API metadata của Hugging Face (`/api/models/skytnt/anime-seg`) xác nhận thuộc tính `cardData.license = "apache-2.0"` và danh mục `tags` chứa định danh công khai `"license:apache-2.0"`.

#### Phân tích Pháp lý: Điều khoản Phi thương mại của Dataset và Giới hạn Lây nhiễm lên Trọng số:
Một mối quan ngại thường gặp trong cộng đồng là liệu điều khoản phi thương mại (Non-Commercial) của bộ dữ liệu DIS5K gốc có "lây nhiễm" sang trọng số mô hình `isnetis.onnx` do SkyTNT tinh chỉnh hay không. Dưới góc độ phân tích pháp lý và kỹ thuật:
1. **Bản chất Số học của Trọng số:** Trọng số mạng nơ-ron là các ma trận số thực dấu phẩy động (`float32`) đại diện cho các tham số hàm số toán học thu được qua quá trình tối ưu hóa hàm mất mát (loss optimization). Trọng số không chứa đựng bản sao chép trực tiếp từng phần hay toàn phần của các bức ảnh đầu vào trong tập dữ liệu.
2. **Điều khoản NC của Dataset không tự động trở thành Giấy phép của Trọng số:** Về nguyên lý bản quyền, các điều khoản hạn chế phi thương mại ràng buộc việc tiếp cận, tải về và phân phối chính tập dữ liệu DIS5K không tự động biến đổi thành giấy phép bản quyền của trọng số mô hình được đào tạo như một tác phẩm phái sinh (derivative work), trừ khi người đào tạo có thỏa thuận hợp đồng trực tiếp (privity of contract) ràng buộc quyền đối với kết quả đầu ra.
3. **Các Lập luận Pháp lý và Giới hạn Bắt buộc (Qualified Legal Analysis):**
   - Một số quan điểm pháp lý lập luận rằng việc đào tạo AI là hành vi trích xuất đặc trưng thống kê phi biểu đạt (non-expressive use) được bảo vệ bởi học thuyết Fair Use (Hoa Kỳ §107), Điều 30-4 Đạo luật Bản quyền Nhật Bản (cho phép khai thác tác phẩm phục vụ phân tích thông tin), hoặc các ngoại lệ Khai thác Văn bản và Dữ liệu (TDM) theo Chỉ thị Bản quyền Thị trường Số Đơn nhất của EU (Chỉ thị DSM, Điều 3 & 4).
   - **Tuy nhiên, đây KHÔNG PHẢI là kết luận pháp lý tuyệt đối hay phổ quát:** Án lệ và khung pháp lý điều chỉnh việc sử dụng dữ liệu có bản quyền để huấn luyện AI trên toàn cầu vẫn đang trong quá trình định hình, liên tục phát sinh tranh chấp và kiện tụng chưa có hồi kết tại nhiều khu vực tài phán. Ngoại lệ TDM của EU cho phép chủ sở hữu quyền tuyên bố bảo lưu quyền (opt-out), và phạm vi áp dụng Fair Use tại Hoa Kỳ đối với các tác vụ thị giác máy tính vẫn có thể bị xem xét lại tùy theo bối cảnh thương mại cụ thể.
4. **Yêu cầu Bắt buộc về Đánh giá Pháp lý Thương mại (Commercial Legal Review Requirement):**
   - Báo cáo này ghi nhận các bằng chứng kỹ thuật và phân tích học thuật nêu trên nhằm phục vụ định hướng kiến trúc, **tuyệt đối không đưa ra kết luận pháp lý tài phán tối hậu** thay thế cho ý kiến tư vấn từ luật sư chuyên trách sở hữu trí tuệ.
   - **Bất kỳ kế hoạch phân phối thương mại (commercial distribution) nào trong tương lai đều bắt buộc phải trải qua quy trình rà soát và đánh giá pháp lý độc lập** theo luật định tại các thị trường phát hành mục tiêu.

### 3.5 Chiến lược Kiến trúc "Bring-Your-Own-Model" (BYOM) & Giới Hạn Pháp Lý
Nhằm giảm thiểu rủi ro trực tiếp trong phân phối mã nguồn và tách biệt trách nhiệm quản trị file nhị phân:
1. **Không phân phối kèm file nhị phân mô hình trong kho mã nguồn Git hoặc gói cài đặt:** Kho lưu trữ của Project AIC chỉ lưu trữ mã nguồn Python tuân thủ hợp đồng và thuật toán xác minh.
2. **Cơ chế BYOM (Bring-Your-Own-Model):** Người dùng hoặc quản trị viên hệ thống chủ động cung cấp tệp mô hình vào thư mục `data/models/isnet-anime.onnx` hoặc chạy lệnh CLI tường minh để tải về, tự chịu trách nhiệm rà soát và tuân thủ các điều khoản cấp phép của bên thứ ba.
3. **Giới hạn của Chiến lược BYOM:** Cần khẳng định rõ ràng rằng **chiến lược BYOM KHÔNG loại bỏ hoàn toàn mọi rủi ro về bản quyền hay cấp phép (does NOT eliminate all copyright or licensing risks)**, đặc biệt khi hệ thống được đóng gói, phân phối thương mại hoặc cung cấp dưới dạng dịch vụ. BYOM chỉ là biện pháp phòng vệ kiến trúc nhằm tách rời việc phân phối mã nguồn khỏi việc phân phối trọng số nhị phân.
4. **Phân phối thương mại vẫn yêu cầu đánh giá pháp lý:** Việc phân phối thương mại hệ thống vẫn đòi hỏi đánh giá pháp lý thích hợp từ chuyên gia sở hữu trí tuệ độc lập.
5. **Tính tương thích với các mô hình thương mại thay thế:** Giao diện `BackgroundRemovalProvider` cho phép cắm ghép (pluggable) bất kỳ mô hình nào khác có chứng nhận thương mại 100% trong tương lai (ví dụ: BRIA RMBG 1.4/2.0 hoặc BiRefNet) mà không phải sửa đổi luồng điều phối của Worker.

### 3.6 Ghim Phiên bản Ổn định Hugging Face, Thông số Kỹ thuật & Dấu vân tay Mật mã SHA-256

Nhằm bảo đảm tính tái lập (reproducibility) và loại bỏ rủi ro chuỗi cung ứng khi kho lưu trữ upstream có thay đổi, Project AIC thực hiện **ghim cố định (pinning) một revision cụ thể** thay vì trỏ vào nhánh `main` biến động:

| Thuộc tính Kỹ thuật | Giá trị Kiểm toán Khách quan & Cố định |
|---|---|
| **Kho lưu trữ Hugging Face** | [`skytnt/anime-seg`](https://huggingface.co/skytnt/anime-seg) |
| **Mã Revision Cố định (Pinned Commit SHA)** | `493cb60893f47441b26ec4fb9a306bce9e342982` (Bản commit xác nhận giấy phép Apache-2.0) |
| **Tên tệp định danh chuẩn** | `isnetis.onnx` (trên Hugging Face) / `isnet-anime.onnx` (trên GitHub rembg) |
| **Kích thước tệp chính xác** | **176,069,933 bytes** (~176.07 MB) |
| **Mã băm mật mã SHA-256** | `f15622d853e8260172812b657053460e20806f04b9e05147d49af7bed31a6e99` |
| **Con trỏ Git LFS OID** | `f15622d853e8260172812b657053460e20806f04b9e05147d49af7bed31a6e99` (Khớp 1:1 với SHA-256 của file nhị phân) |
| **Phiên bản ONNX IR / Opset** | IR Version 7, Opset Version 11 |
| **Tên Tensor Đầu vào (Input)** | `"img"` |
| **Hình dạng Tensor Đầu vào** | `[1, 3, 1024, 1024]` (Batch=1, Kênh=3 RGB, Cao=1024, Rộng=1024, kiểu `float32`, bố cục NCHW) |
| **Khoảng giá trị Đầu vào** | Chuẩn hóa `[0.0, 1.0]` (kèm phân phối ImageNet mean/std) |
| **Tên Tensor Đầu ra (Output)** | `"mask"` |
| **Hình dạng Tensor Đầu ra** | `[1, 1, 1024, 1024]` (Batch=1, Kênh=1, Cao=1024, Rộng=1024, kiểu `float32`) |
| **Bản chất Tensor Đầu ra** | Điểm kích hoạt xác suất liên tục $\in [0.0, 1.0]$ biểu diễn độ đục của nhân vật foreground |

#### Đường dẫn Tải về Chính thức Được Ghim Chặt (Pinned Source URLs):
- **Điểm cuối chính xác ghim commit (Primary Pinned URL):**  
  `https://huggingface.co/skytnt/anime-seg/resolve/493cb60893f47441b26ec4fb9a306bce9e342982/isnetis.onnx`
- **Điểm cuối dự phòng thứ cấp (Secondary Fallback URL):**  
  `https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-anime.onnx`  
  *(Cùng kích thước 176,069,933 bytes và mã băm SHA-256 `f15622d8...`)*

### 3.7 Thuật toán Xác minh Băm SHA-256 Dạng Luồng và Cơ chế Cách ly Sự cố

#### Bất biến Bắt buộc Trước khi Nạp Mô hình (Pre-Load Invariant):
> **Bất biến:** Phiên làm việc của ONNX Runtime (`ort.InferenceSession`) TUYỆT ĐỐI KHÔNG ĐƯỢC PHÉP mở bất kỳ tệp mô hình nào trên ổ đĩa nếu tệp đó chưa vượt qua bước tính toán và xác minh mã băm SHA-256 đối chiếu với giá trị chuẩn.

#### Thuật toán Tính Băm Dạng Luồng Tiết kiệm RAM:
```python
import hashlib
from pathlib import Path


class ModelIntegrityError(Exception):
  """Ngoại lệ ném ra khi tệp mô hình bị lỗi toàn vẹn hoặc không khớp mã băm."""

  pass


def verify_model_sha256(
    file_path: Path,
    expected_sha256: str,
    chunk_size_bytes: int = 1024 * 1024,  # Đọc từng khối 1 MB
) -> bool:
  """Xác thực mã băm SHA-256 của file mô hình qua cơ chế đọc luồng đệm.

  Tránh đọc toàn bộ 176 MB vào RAM một lúc, bảo vệ tài nguyên hệ thống.
  """
  if not file_path.is_file():
    raise FileNotFoundError(f"Không tìm thấy file mô hình tại: {file_path}")

  hasher = hashlib.sha256()
  with open(file_path, "rb") as f:
    while chunk := f.read(chunk_size_bytes):
      hasher.update(chunk)

  computed_hash = hasher.hexdigest().lower()
  return computed_hash == expected_sha256.strip().lower()
```

#### Quy trình Xử lý Sự cố Sai lệch Mã băm (Quarantine Policy):
1. **Lập tức Từ chối Nạp (Fail-Closed Execution):** Ném ngoại lệ `ModelIntegrityError`. Tác vụ xử lý ảnh lập tức dừng lại, ghi nhận trạng thái lỗi `failed` và chuyển sang Dead Letter Queue (DLQ). Tuyệt đối không bao giờ cố gắng nạp một tệp tin hỏng.
2. **Cách ly Tệp Hỏng (Quarantine Action):** Di chuyển tệp tin lỗi ra khỏi thư mục hoạt động sang thư mục cách ly: `data/models/quarantine/<timestamp>_<filename>.corrupted`. Thao tác này ngăn chặn các worker hoặc luồng khác tiếp tục truy cập vào tệp tin độc hại/hỏng hóc. Nếu không thể di chuyển, thực hiện xóa bỏ an toàn (`unlink`).
3. **Ghi Nhật ký Kiểm toán An ninh (Audit Logging):** Ghi log mức độ `CRITICAL` với đầy đủ thông tin: đường dẫn tệp, kích thước byte thực tế, mã băm tính được, mã băm kỳ vọng và dấu thời gian.

### 3.8 Quy định Tuyệt đối: Cấm Tự động Tải Mô hình khi Khởi động hoặc Import
Một lỗi kiến trúc rất phổ biến ở các thư viện mã nguồn mở là tự động kích hoạt tiến trình tải file qua mạng ngay khi người dùng thực hiện câu lệnh `import` hoặc khi server FastAPI bắt đầu khởi động.

**Project AIC nghiêm cấm hành vi này thông qua các nguyên tắc sau:**
1. **Zero Side-Effects khi Import:** Lệnh `import backend.app.pipeline.background` phải hoàn tất tức thì trong vài mili-giây, không tiêu tốn băng thông mạng và hoạt động bình thường ngay cả trong môi trường cô lập mạng hoàn toàn (Air-gapped).
2. **Khởi động Server Độc lập:** Khởi động backend (`uvicorn app.main:app`) tuyệt đối không kiểm tra mạng để tải mô hình. Nếu cấu hình chọn ONNX nhưng thiếu tệp mô hình, hệ thống ghi nhận trạng thái cảnh báo và từ chối tác vụ khi được yêu cầu, chứ không làm sập server.
3. **Cung cấp Mô hình Ngoài luồng qua CLI Tường minh (Out-of-Band CLI):** Việc tải mô hình chỉ được phép diễn ra khi quản trị viên chủ động chạy lệnh CLI tường minh:
   ```powershell
   uv run python -m app.cli.pipeline download-model --model isnet-anime
   ```
   Lệnh CLI này tích hợp `SafeDownloader`, xác thực tên miền tin cậy (`huggingface.co`), tải về tệp tạm `.tmp.<uuid>`, kiểm tra khớp SHA-256 rồi mới đổi tên nguyên tử thành `isnet-anime.onnx`.

---

## 4. CHẤT LƯỢNG HÌNH ẢNH ANIME & KIẾN TRÚC MẶT NẠ ALPHA (Quality & Alpha Matting)

### 4.1 Phân tích 6 Trường hợp Biên (Edge Cases) Đặc thù Của Tranh Anime

```
               6 TRƯỜNG HỢP BIÊN QUANG HỌC CỦA TRANH ANIME
┌─────────────────────────────────┬─────────────────────────────────┐
│ 1. Sợi Tóc Mai & Cọng Tóc Nhọn   │ 2. Vòng Hào Quang Tóc Specular   │
│    (Ahoge & Thin Strands)       │    (Angel Rings / Hair Clumps)  │
│    - Rộng chỉ 1-3 pixel         │    - Dải sáng trắng dễ bị lủng  │
├─────────────────────────────────┼─────────────────────────────────┤
│ 3. Phụ Kiện Nơ & Chi Tiết Lơ Lửng│ 4. Vùng Bán Trong Suốt          │
│    (Ribbons, Ears, Charms)      │    (Kính, Vải Voan, Cánh Mỏng)  │
│    - Dễ bị bóc nhầm thành rác   │    - Đòi hỏi Alpha liên tục     │
├─────────────────────────────────┼─────────────────────────────────┤
│ 5. Nét Viền Mực & Chảy Màu Nền   │ 6. Khe Hở Trang Phục Phức Tạp   │
│    (Line Art Inking & Halos)    │    (Nếp Váy, Ren, Khoảng Hở Tay)│
│    - Cần bám chuẩn tim nét vẽ   │    - Cần bóc sạch nền xuyên thấu│
└─────────────────────────────────┴─────────────────────────────────┘
```

1. **Sợi tóc mai mảnh & Tóc nhọn (Ahoge & Fine Hair Strands):** Chiều rộng chỉ từ 1 đến 3 pixel vươn ra ngoài nền. Các mô hình thông thường downsample dễ làm gãy rụng các sợi tóc này. IS-Net được thiết kế nhằm khắc phục nhược điểm này nhờ độ phân giải đầu vào cao $1024 \times 1024$ bảo tồn đặc trưng không gian tần số cao hơn (hiệu quả thực tế sẽ được kiểm chứng bằng benchmark ở Phase 0.5B).
2. **Vòng hào quang tóc ("Angel Rings" Highlights):** Dải sáng trắng hoặc pastel bóng loáng trên đỉnh đầu Miku. Khi nền ảnh gốc là màu trắng sáng, các mạng phân vùng cổ điển thường nhận nhầm dải sáng này là nền xuyên thấu, tạo ra các lỗ thủng kỳ dị trên đầu nhân vật. Tầm nhìn ngữ cảnh toàn cục của IS-Net được thiết kế nhằm phân biệt đây là cấu trúc bên trong khối tóc thay vì phông nền.
3. **Phụ kiện nơ bay và trang sức nổi:** Nơ tai nghe Miku, ruy-băng lơ lửng có diện tích nhỏ dễ bị các bộ lọc hình thái học (morphological filter) xóa bỏ do coi là nhiễu. Thiết kế ngưỡng giữ lại alpha mềm ở mức thấp ($T_{\text{low}} \le 0.05$) nhằm tối ưu khả năng bảo tồn chi tiết phụ kiện mảnh.
4. **Vùng bán trong suốt (Semi-transparent Veils & Glasses):** Mắt kính, tất ren mỏng, cánh cơ khí mờ ảo. Việc sử dụng mặt nạ nhị phân cứng (chỉ có 0 hoặc 255) sẽ biến vải voan mỏng thành một tấm bìa cứng đục ngầu hoặc xóa mất tròng kính. Việc duy trì kênh alpha mềm liên tục $\alpha \in [0.0, 1.0]$ là điều kiện tiên quyết trong thiết kế hậu xử lý.
5. **Nét viền mực đen (Line Art Inking):** Nét mực dày 1-2 pixel bao quanh nhân vật. Nếu mặt nạ co vào 1 pixel sẽ làm mất nét mực (nhân vật trông xơ xác, sắc nhọn); nếu nở ra 1 pixel sẽ dính viền màu của phông nền cũ (halo artifact). Cần thuật toán ánh xạ tọa độ unpadding chuẩn xác từng pixel để bảo toàn nét vẽ.
6. **Khe hở trang phục phức tạp (Costume Cavities):** Khoảng hở giữa cánh tay chống nạnh, kẽ giữa hai lọn tóc twintail và thân người, nếp gấp váy xếp ly. Khả năng kết hợp đa tầng đặc trưng của IS-Net được kỳ vọng hỗ trợ bóc tách nền bên trong các hốc rỗng mà không làm thủng trang phục (chất lượng thực tế cần kiểm chứng qua tập kiểm chuẩn).

### 4.2 Thiết kế Tiền xử lý: Phép thử Bảo toàn Hình học (Geometry Preservation Test) vs. Chất lượng Phân vùng AI

> **Cảnh báo Thiết kế Cốt lõi:** Tuyệt đối nghiêm cấm việc dùng lệnh resize kéo giãn ảnh trực tiếp về $1024 \times 1024$. Thao tác này sẽ bóp méo tỷ lệ cơ thể nhân vật, làm sai lệch các bộ lọc tích chập và gây ra hiện tượng méo mặt Miku.

Quy trình tiền xử lý toán học bắt buộc phải sử dụng **đệm khung đối xứng (Symmetrical Letterboxing)**:
1. Tính hệ số co dãn bảo toàn tỷ lệ:
   $$s = \min\left(\frac{1024}{W_{\text{orig}}}, \frac{1024}{H_{\text{orig}}}\right)$$
2. Kích thước ảnh sau khi co dãn:
   $$W_{\text{new}} = \text{round}(W_{\text{orig}} \cdot s), \quad H_{\text{new}} = \text{round}(H_{\text{orig}} \cdot s)$$
3. Tọa độ đệm lề đối xứng (Symmetrical padding offsets):
   $$\Delta x = \left\lfloor \frac{1024 - W_{\text{new}}}{2} \right\rfloor, \quad \Delta y = \left\lfloor \frac{1024 - H_{\text{new}}}{2} \right\rfloor$$
4. Dán ảnh đã co dãn vào giữa canvas $1024 \times 1024$ nền đen `(0, 0, 0)` hoặc xám trung tính `(128, 128, 128)`.
5. Chuẩn hóa ma trận điểm ảnh sang `float32` trong khoảng $[0.0, 1.0]$, áp dụng phân phối ImageNet ($\mu = [0.485, 0.456, 0.406], \sigma = [0.229, 0.224, 0.225]$), chuyển trục từ HWC sang NCHW `(1, 3, 1024, 1024)`.

```python
def preprocess_letterbox(
    img: Image.Image,
    target_size: int = 1024,
) -> tuple[np.ndarray, dict[str, int]]:
  """Đệm khung đối xứng letterbox về [1, 3, 1024, 1024] và chuẩn hóa ImageNet."""
  rgb_img = img.convert("RGB")
  w_orig, h_orig = rgb_img.size

  scale = min(target_size / w_orig, target_size / h_orig)
  w_new = max(1, round(w_orig * scale))
  h_new = max(1, round(h_orig * scale))

  resized = rgb_img.resize((w_new, h_new), Image.Resampling.BILINEAR)

  pad_x = (target_size - w_new) // 2
  pad_y = (target_size - h_new) // 2

  canvas = Image.new("RGB", (target_size, target_size), (0, 0, 0))
  canvas.paste(resized, (pad_x, pad_y))

  # Chuyển đổi sang float32 [0.0, 1.0] và chuẩn hóa phân phối ImageNet
  arr = np.array(canvas, dtype=np.float32) / 255.0
  mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
  std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
  norm_arr = (arr - mean) / std

  # Chuyển trục HWC -> CHW -> NCHW (1, 3, 1024, 1024)
  tensor = np.transpose(norm_arr, (2, 0, 1))
  tensor = np.expand_dims(tensor, axis=0)

  pad_meta = {
      "pad_x": pad_x,
      "pad_y": pad_y,
      "w_new": w_new,
      "h_new": h_new,
      "w_orig": w_orig,
      "h_orig": h_orig,
  }
  return tensor, pad_meta
```

#### Phân định Rạch ròi: Phép thử Bảo toàn Hình học (Geometry Preservation Test)
Trong quá trình thử nghiệm thuật toán lưới tọa độ, một bài kiểm tra độ lệch tọa độ khứ hồi (Round-Trip Coordinate Projection Test) đã được thực hiện trên **17 kích thước và tỷ lệ khung hình đại diện**:
- Nhóm ảnh vuông: $512 \times 512$, $1024 \times 1024$.
- Nhóm chân dung dọc: $600 \times 900$ (2:3), $800 \times 1200$ (chuẩn sprite), $768 \times 1024$ (XGA), $900 \times 1600$ (9:16 mobile), $1080 \times 1920$ (FHD dọc), $1200 \times 1800$ (hi-res).
- Nhóm phong cảnh ngang: $800 \times 600$ (4:3), $1024 \times 768$ (XGA ngang), $1280 \times 720$ (HD), $1920 \times 1080$ (FHD ngang), $2048 \times 1536$ (iPad 4:3), $2560 \times 1440$ (2K), $3840 \times 2160$ (4K UHD).
- Nhóm tỷ lệ cực đoan: $2560 \times 1080$ (Ultra-wide 21:9), $1080 \times 2560$ (Ultra-tall 9:21).

Kết quả ghi nhận: Sai số lệch tọa độ giữa điểm gốc $(x, y)$ và điểm sau khi chiếu qua canvas $1024 \times 1024$ rồi unpad ngược trở lại là **$\le 0.081\text{ px}$** (hoàn toàn nằm trong sai số làm tròn số thực dấu phẩy động sub-pixel).

> **NGUYÊN TẮC PHÂN ĐỊNH BẮT BUỘC:**  
> Bài kiểm tra sai số $\le 0.081\text{ px}$ này **THUẦN TÚY LÀ BÀI TOÁN BẢO TOÀN HÌNH HỌC (Geometry Preservation Test)**, xác nhận tính chính xác số học của các hàm resize, padding và unpadding.  
> **TUYỆT ĐỐI KHÔNG ĐƯỢC PHÉP** sử dụng kết quả bảo toàn hình học này để minh chứng hay bảo đảm cho chất lượng phân vùng bóc tách nền của mô hình AI! Việc tọa độ khung hình không bị méo lệch hoàn toàn không chứng minh được mô hình AI có nhận diện đúng sợi tóc, có cắt đứt nét nơ áo hay có phân biệt được màu tóc với màu phông nền hay không.

### 4.3 Thiết kế Hậu xử lý: Mặt nạ Alpha Mềm (Soft Alpha) và Khôi phục Tọa độ Gốc

Sau khi mô hình ONNX xuất ra tensor mặt nạ thô `(1, 1, 1024, 1024)`:
1. **Kiểm tra và Khử Logits:** Nếu giá trị cực tiểu $< 0.0$ hoặc cực đại $> 1.0$, áp dụng hàm Sigmoid ổn định số học:
   $$\text{prob}(x, y) = \frac{1}{1 + e^{-\text{clip}(z(x, y), -20.0, 20.0)}}$$
2. **Cắt bỏ Phần Đệm Lề (Crop Padding):** Cắt chính xác vùng ma trận ảnh thực tế:
   $$\text{cropped\_prob} = \text{prob}[\Delta y : \Delta y + H_{\text{new}}, \; \Delta x : \Delta x + W_{\text{new}}]$$
3. **Thu phóng Trở lại Tọa độ Gốc (Bilinear Unpadding):** Phóng to `cropped_prob` trở lại kích thước ban đầu $(W_{\text{orig}}, H_{\text{orig}})$ bằng phép nội suy song tuyến tính (`Image.Resampling.BILINEAR`). Thao tác này khôi phục lưới tọa độ mặt nạ về đúng độ phân giải gốc của ảnh ban đầu (kết hợp với đệm đối xứng đạt sai số hình học sub-pixel $\le 0.081\text{ px}$; phân định rõ đây là bảo toàn hình học, không phải chứng minh chất lượng phân vùng AI).
4. **Hàm Chuyển đổi Dải Alpha Mềm (Continuous Soft Alpha Ramp):**
   Thay vì cắt ngưỡng nhị phân cứng ở 0.5 gây răng cưa, áp dụng hàm chuyển tiếp làm mịn:
   $$A(x, y) = \begin{cases} 
   0 & \text{khi } p(x, y) \le T_{\text{low}} \\
   255 & \text{khi } p(x, y) \ge T_{\text{high}} \\
   \text{round}\left(255 \cdot \frac{p(x, y) - T_{\text{low}}}{T_{\text{high}} - T_{\text{low}}}\right) & \text{khi } T_{\text{low}} < p(x, y) < T_{\text{high}}
   \end{cases}$$
   Với ngưỡng tiêu chuẩn kiểm nghiệm: $T_{\text{low}} = 0.05$ và $T_{\text{high}} = 0.95$.

```python
def postprocess_mask(
    raw_mask: np.ndarray,
    pad_meta: dict[str, int],
    orig_size: tuple[int, int],
    t_low: float = 0.05,
    t_high: float = 0.95,
) -> Image.Image:
  """Hậu xử lý unpad, sigmoid và chuyển tiếp dải alpha mềm liên tục."""
  mask = np.squeeze(raw_mask)  # [1024, 1024]

  # Khử logits nếu tensor đầu ra chưa nằm trong khoảng xác suất [0.0, 1.0]
  if mask.min() < 0.0 or mask.max() > 1.0:
    mask = 1.0 / (1.0 + np.exp(-np.clip(mask, -20.0, 20.0)))

  # Cắt bỏ phần viền đệm (Crop Padding)
  pad_x = pad_meta["pad_x"]
  pad_y = pad_meta["pad_y"]
  w_new = pad_meta["w_new"]
  h_new = pad_meta["h_new"]
  cropped_prob = mask[pad_y : pad_y + h_new, pad_x : pad_x + w_new]

  # Phóng to trở lại kích thước gốc bằng Bilinear Unpadding
  prob_img = Image.fromarray((cropped_prob * 255.0).astype(np.uint8))
  w_orig, h_orig = orig_size
  unpadded_img = prob_img.resize((w_orig, h_orig), Image.Resampling.BILINEAR)
  prob_arr = np.array(unpadded_img, dtype=np.float32) / 255.0

  # Áp dụng hàm chuyển tiếp dải Alpha mềm (Continuous Soft Alpha Ramp)
  alpha = np.zeros_like(prob_arr, dtype=np.uint8)
  mid_mask = (prob_arr > t_low) & (prob_arr < t_high)
  alpha[prob_arr >= t_high] = 255
  alpha[mid_mask] = np.round(
      255.0 * (prob_arr[mid_mask] - t_low) / (t_high - t_low)
  ).astype(np.uint8)

  return Image.fromarray(alpha)
```

### 4.4 Bộ lọc Tinh chỉnh Cạnh Biên Tùy chọn (Guided Filter)
Bộ lọc Guided Image Filter có thể dùng ảnh RGB gốc làm ảnh dẫn đường (guide image) để định hình lại kênh alpha mờ. Thuật toán giả định mối quan hệ tuyến tính giữa cường độ màu của ảnh gốc và độ đục alpha trong cửa sổ lân cận hẹp $\omega_k$: $\alpha_i = a_k I_i + b_k$. Theo lý thuyết xử lý ảnh, bộ lọc có tiềm năng cải thiện độ sắc nét dải biên cho các sợi tóc mảnh, tuy nhiên có chi phí tính toán khoảng 15–40 ms trên CPU. Bộ lọc này được đề xuất dưới dạng tùy chọn cấu hình (`enable_guided_filter=False` mặc định).

### 4.5 Khởi tạo Luồng Byte RGBA Đích Thực (4 Kênh Chuẩn PNG)
Gán kênh Alpha mềm đã chuẩn hóa $(A)$ trực tiếp vào ảnh RGB gốc bằng phương thức tối ưu `putalpha()` của Pillow (tự động xử lý an toàn mọi định dạng màu ban đầu như RGB, RGBA, Palette hay Grayscale mà không gây lỗi unpack kênh):
```python
# Đảm bảo ảnh gốc ở không gian màu RGB trước khi áp dụng alpha
rgb_image = orig_image.convert("RGB")
rgba_image = rgb_image.copy()
rgba_image.putalpha(alpha_channel)
buffer = io.BytesIO()
rgba_image.save(buffer, format="PNG", optimize=True)
transparent_png_bytes = buffer.getvalue()
```
Đầu ra này tương thích với giai đoạn tiếp theo của Pipeline: `SpriteNormalizer` sẽ trích xuất `img.getchannel("A").getbbox()`, tính toán tỷ lệ co dãn thích hợp và đặt nhân vật lên canvas chuẩn $1024 \times 1536$ theo đúng hợp đồng dữ liệu hiện hữu.

### 4.6 4 Cổng Kiểm chuẩn Đầu ra: Cơ sở Lý thuyết, Điều kiện Loại bỏ Nhầm & Phương pháp Hiệu chuẩn

Nhà cung cấp dịch vụ tách nền thực thi 4 bước kiểm định tự động trước khi bàn giao luồng byte cho hệ thống:

```python
def validate_alpha_matte(
    alpha: Image.Image,
    allow_translucent: bool = False,
    allow_full_bleed: bool = False,
    min_coverage: float = 0.05,
    max_coverage: float = 0.98,
    min_dimension: int | None = None,
) -> tuple[bool, str | None, list[str]]:
  """Kiểm định 4 cổng chất lượng mặt nạ alpha với các cờ hiệu chuẩn linh hoạt."""
  warnings: list[str] = []
  extrema = alpha.getextrema()
  if extrema is None:
    return False, "Kênh Alpha không có dữ liệu.", warnings

  min_a, max_a = extrema
  # Cổng 1: Kiểm tra cực trị (Phải có cả điểm trong suốt và điểm đục)
  required_max_alpha = 180 if allow_translucent else 250
  if max_a < required_max_alpha:
    return (
        False,
        "Mặt nạ rỗng hoặc quá mờ: không phát hiện vùng nhân vật đục đặc ruột"
        f" (max_alpha={max_a} < {required_max_alpha}).",
        warnings,
    )
  required_min_alpha = 255 if allow_full_bleed else 5
  if min_a > required_min_alpha:
    return (
        False,
        "Mặt nạ đục hoàn toàn: không tách được phông nền trong suốt"
        f" (min_alpha={min_a} > {required_min_alpha}).",
        warnings,
    )

  # Cổng 2: Kiểm tra kích thước hộp bao (Bounding Box thích ứng)
  bbox = alpha.getbbox()
  if bbox is None:
    return False, "Không phát hiện vùng nhân vật trong kênh Alpha.", warnings
  bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
  effective_min_dim = (
      min_dimension
      if min_dimension is not None
      else max(32, int(0.08 * min(alpha.size)))
  )
  if bw < effective_min_dim or bh < effective_min_dim:
    return (
        False,
        f"Hộp bao quá nhỏ ({bw}x{bh} < {effective_min_dim}x{effective_min_dim}): nghi ngờ đốm nhiễu.",
        warnings,
    )

  # Cổng 3: Tỷ lệ bao phủ diện tích nhân vật (Silhouette Coverage Ratio)
  arr = np.array(alpha, dtype=np.uint8)
  coverage = float(np.count_nonzero(arr > 12) / arr.size)
  effective_max_cov = 1.0 if allow_full_bleed else max_coverage
  if coverage < min_coverage:
    return (
        False,
        f"Độ phủ nhân vật ({coverage:.3%}) quá thấp dưới mức cho phép ({min_coverage:.1%}).",
        warnings,
    )
  if coverage > effective_max_cov:
    return (
        False,
        f"Độ phủ nhân vật ({coverage:.3%}) vượt quá {effective_max_cov:.1%}, phông nền chưa được xóa sạch.",
        warnings,
    )

  # Cổng 4: Kiểm tra sự tồn tại của dải giá trị chuyển tiếp (Soft Gradient)
  hist = alpha.histogram()
  has_soft_edge = any(hist[i] > 0 for i in range(10, 245))
  if not has_soft_edge:
    # Cảnh báo viền nhị phân cứng: không từ chối cứng mà ghi nhận cảnh báo chẩn đoán
    warnings.append("soft_alpha_missing")

  return True, None, warnings
```

#### Bảng Kiểm toán Chi tiết: Cơ sở Lý thuyết, Tình huống Loại bỏ Nhầm & Phương án Hiệu chuẩn:

| Cổng Kiểm chuẩn & Ngưỡng | Cơ sở Lý luận Kỹ thuật (Rationale) | Điều kiện Gây Loại Bỏ Nhầm (False Rejection Condition) | Phương pháp Hiệu chuẩn & Khắc phục (Calibration Method) |
|---|---|---|---|
| **`min_alpha <= 5`** | Đảm bảo bức ảnh có ít nhất một vùng phông nền đã được bóc tách thành trong suốt tuyệt đối (hoặc gần như tuyệt đối $\le 5/255$). Ngăn chặn ảnh hoàn toàn đục chưa tách nền. | **Ảnh chân dung cận cảnh góc cực hẹp (Extreme Macro Close-up):** Khung hình chụp cận cảnh khuôn mặt hoặc mắt Miku choán kín 100% canvas, không hề có bất kỳ pixel phông nền nào lọt vào. | Kiểm tra phân loại tư thế `AnchorType.EYE_LEVEL`. Nếu nhân vật chiếm trọn khung hình hợp lệ, cho phép nới lỏng hoặc tạm miễn trừ kiểm tra `min_alpha` thông qua tham số gọi hàm. |
| **`max_alpha >= 250`** | Đảm bảo nhân vật có khối lượng cơ thể đặc ruột (opaque solid core $\ge 250/255$), ngăn chặn lỗi mô hình biến toàn bộ nhân vật thành bóng ma mờ ảo. | **Nhân vật dạng linh hồn, ảo ảnh hoặc cánh năng lượng:** Các thiết kế Miku dạng hologram trong suốt, linh hồn mờ ảo hoặc cánh cơ khí bán trong suốt có chủ đích nghệ thuật với $\alpha_{\max} < 240$. | Thiết lập cờ cấu hình `allow_translucent_character=True` trong `kwargs` khi xử lý các asset hiệu ứng đặc biệt để hạ ngưỡng kiểm tra xuống $180$. |
| **`bbox >= 64x64`** | Loại trừ các mảnh vụn nhiễu cô lập (dust/noise artifacts) phát sinh khi nền phức tạp bị bóc nhầm nhưng nhân vật chính đã bị xóa sạch. | **Sticker chibi siêu nhỏ hoặc phụ kiện rời:** Các icon cảm xúc mini (32x32), sticker linh vật thu nhỏ, hoặc phụ kiện trôi nổi trong các bộ sprite phụ trợ. | Chuyển ngưỡng tuyệt đối $64\text{px}$ sang ngưỡng thích ứng tỷ lệ: $\text{min\_dim} \ge \max(32, 0.08 \times \min(W_{\text{orig}}, H_{\text{orig}}))$. |
| **`coverage in [0.05, 0.98]`** | Ngưỡng chặn diện tích nhân vật: $< 5\%$ cho thấy nhân vật bị cắt mất gần hết; $> 98\%$ cho thấy phông nền ngoại cảnh chưa được loại bỏ. | **Ảnh toàn cảnh viễn cảnh (Extreme Wide-shot) hoặc Tranh tràn viền (Full-bleed):** Nhân vật đứng rất xa giữa phong cảnh chỉ chiếm $3-4\%$ diện tích; hoặc tranh minh họa poster nhân vật chiếm $98.5\%$ diện tích canvas. | Thu thập tập mẫu 500 ảnh sprite Miku để vẽ đường cong phân phối diện tích thực tế; cho phép điều chỉnh dải ngưỡng theo tỷ lệ khung hình và nhãn tư thế (`AnchorType`). |
| **`soft_alpha_distribution`** | Kiểm tra sự tồn tại của điểm ảnh chuyển tiếp ($10 \le \alpha \le 245$) nhằm bảo đảm dải viền mềm mại, không bị răng cưa (aliasing) trên tóc mai và vải mỏng. | **Tranh Pixel Art hoặc Cel-shading cổ điển:** Tranh vẽ phong cách retro pixel art hoặc tranh cel-shading cố ý giữ nét mực viền nhị phân cứng 1-bit theo phong cách nghệ thuật tác giả. | Thiết kế cổng này dưới dạng **Cảnh báo Chẩn đoán (Diagnostic Warning)** ghi vào metadata `warnings: ["soft_alpha_missing"]` thay vì ném ngoại lệ từ chối cứng (Hard Rejection). |

### 4.7 Kế hoạch Benchmark Chất lượng Phân vùng AI & Giới hạn của Các Chỉ số Định lượng

Nhằm đánh giá năng lực bóc tách thực tế của mô hình IS-Net Anime trong giai đoạn tiếp theo, hệ thống thiết lập kế hoạch đo kiểm chuyên sâu (AI Segmentation Quality Benchmark Plan) bao phủ toàn diện các thách thức quang học đặc thù của phong cách tranh anime:

#### 1. Ma trận 6 Nhóm Ca Kiểm Thử Biên Chuyên Sâu:
1. **Tóc mai mảnh và lọn tóc dài (Fine Hair & Long Hair):** Ahoge đỉnh đầu rộng 1–3 pixel, lọn tóc twintail xòe rộng bay trong gió, các sợi tóc mai bay lơ thơ ngoài phông nền.
2. **Nơ và phụ kiện nhỏ (Ribbons & Small Accessories):** Nơ kẹp tai nghe Miku, dây ruy-băng trang phục bay lơ lửng, kẹp tóc số hiệu "01", trang sức cổ tay diện tích nhỏ.
3. **Nét vẽ viền mực và đường bao nhân vật (Line Art & Character Contours):** Nét mực viền đen dày 1–2 pixel bao quanh cơ thể; yêu cầu bám sát đường tim viền vẽ, không làm mỏng nét mực và giảm thiểu tối đa vệt màu nền cũ (halo artifacts).
4. **Vùng bán trong suốt (Semi-transparent Regions):** Khăn voan mỏng, tất ren xuyên thấu, tròng kính cận, cánh cơ khí mờ ảo có dải alpha chuyển tiếp thực tế.
5. **Trang phục phức tạp & Hốc rỗng (Complex Costumes & Cavities):** Váy nhiều tầng xếp ly, diềm đăng-ten ren, khoảng trống xuyên thấu giữa cánh tay chống nạnh và thân người.
6. **Phông nền đơn giản vs. Phông nền phức tạp (Simple vs. Complex Backgrounds):** So sánh hiệu năng bóc tách giữa nền trắng/đơn sắc với cảnh nền ngoại cảnh anime dày đặc chi tiết (đường phố thành phố tương lai, hoa anh đào rực rỡ, lớp học có màu sắc trùng màu tóc xanh ngọc của Miku).

#### 2. Đề xuất Các Chỉ số Đánh giá Định lượng và Phân tích Giới hạn Kỹ thuật:

| Chỉ số Định lượng | Công thức Toán học | Ý nghĩa Đánh giá | Giới hạn Kỹ thuật Cốt lõi (Metric Limitations) |
|---|---|---|---|
| **IoU (Intersection over Union / Jaccard Index)** | $\text{IoU} = \frac{\|A \cap B\|}{\|A \cup B\|}$ | Đo lường tỷ lệ trùng khớp diện tích tổng thể giữa mặt nạ dự đoán $A$ và mặt nạ chuẩn $B$. | **Quá nhạy với diện tích lớn, bỏ qua chi tiết nhỏ:** Do phần thân nhân vật chiếm tới $90\%$ diện tích, một mô hình làm đứt gãy toàn bộ sợi tóc mai 2px vẫn có thể đạt điểm $\text{IoU} > 0.96$. Không phản ánh đúng chất lượng viền tóc. |
| **Dice / F1-Score** | $\text{Dice} = \frac{2\|A \cap B\|}{\|A\| + \|B\|}$ | Đánh giá độ chính xác phân loại điểm ảnh foreground với trọng số cân bằng giữa Precision và Recall. | **Bị chi phối bởi vùng đặc ruột:** Tương tự IoU, điểm số Dice bị chi phối áp đảo bởi các mảng màu lớn bên trong cơ thể nhân vật, ít nhạy cảm với lỗi răng cưa biên hoặc mất phụ kiện mảnh. |
| **Boundary F-score ($F_B$)** | $F_B = \frac{2 \cdot P_B \cdot R_B}{P_B + R_B}$ trên dải biên $\pm d\text{ px}$ | Đo lường độ chính xác phân vùng chỉ riêng tại dải viền bao quanh đường biên tóc và trang phục trong phạm vi bán kính $d$ (ví dụ $d=2\text{px}$). | **Phụ thuộc vào tham số bán kính giãn nở $d$:** Nếu đặt $d$ quá lớn, chỉ số mất tính nhạy với sợi tóc mảnh; nếu đặt $d$ quá nhỏ ($1\text{px}$), sai số làm tròn số thực có thể khiến điểm số sụt giảm nghiêm trọng dù mắt người nhìn vẫn hoàn hảo. |
| **Đánh giá Trực quan Lỗi Viền Cạnh (Visual Edge Artifact Assessment)** | Chấm điểm chuyên gia (Expert Visual Audit) trên thang đo Likert 1–5 | Kiểm tra hiện tượng lem màu viền cũ (color bleeding), quầng sáng (halo), răng cưa (aliasing) và viền xơ xác khi ghép nhân vật lên 2 nền đối lập: đen tuyền `(0,0,0)` và trắng tinh `(255,255,255)`. | **Mang tính chủ quan và khó tự động hóa:** Đòi hỏi mắt nhìn thẩm mỹ của chuyên gia đồ họa, không thể tích hợp làm cổng kiểm thử tự động trong pipeline CI/CD hàng loạt. |

#### 3. Tuyên bố Bắt buộc về Dữ liệu Đo kiểm Định lượng (Ground-Truth Mask Caveat):
> **TUYÊN BỐ TRUNG THỰC KỸ THUẬT:**  
> Hệ thống **KHÔNG THỂ CUNG CẤP CÁC KẾT QUẢ ĐỊNH LƯỢNG CHÍNH XÁC VỀ CHẤT LƯỢNG PHÂN VÙNG AI (Quantitative Segmentation Quality Results)** tại thời điểm báo cáo này.  
> Để tính toán được các chỉ số $\text{IoU}$, $\text{Dice}$, hay $F_B$, toán học bắt buộc phải có **mặt nạ chuẩn đối soát (Ground-Truth Masks $\alpha^*$)** được các chuyên gia đồ họa dán nhãn thủ công chuẩn xác từng pixel cho bộ ảnh nhân vật Hatsune Miku. Mọi khẳng định về độ chính xác phân vùng mà không dựa trên ground-truth mask đều là suy diễn phi thực nghiệm và vi phạm nguyên tắc liêm chính khoa học của dự án.

### 4.8 BẢNG PHÂN ĐỊNH BẮT BUỘC: Sự thật Thực nghiệm vs. Giả thuyết Thiết kế

| Hạng mục / Khẳng định Kỹ thuật | Phân loại Trạng thái | Bằng chứng Thực nghiệm / Phương pháp Đo kiểm | Kết luận Cụ thể |
|---|---|---|---|
| **Hợp đồng BBox của `SpriteNormalizer`** | **Sự thật Thực nghiệm** | `backend/app/pipeline/processing/normalizer.py:20-131`, `test_normalizer_alignment.py` | `SpriteNormalizer` dựa hoàn toàn vào `img.getchannel("A").getbbox()`. Scaling bảo toàn tỷ lệ qua `min(max_w/sil_w, max_h/sil_h)` và neo chuẩn sàn $Y=1511$ hoặc $Y=1536$. |
| **Phép thử Bảo toàn Hình học ($\le 0.081\text{ px}$)** | **Sự thật Thực nghiệm** | Đo kiểm ma trận tọa độ khứ hồi trên 17 tỷ lệ kích thước ảnh | Khẳng định thuật toán co dãn, đệm đối xứng letterbox và unpad đạt sai số sub-pixel $\le 0.081\text{ px}$. **KHÔNG dùng để chứng minh chất lượng bóc nền của AI.** |
| **Cực trị Alpha của Mock Provider** | **Sự thật Thực nghiệm** | `backend/app/pipeline/background/mock_provider.py:125-128`, `test_mock_background.py` | Mock provider khẳng định `final_extrema == (0, 255)`. Kiểm thử xác nhận `hist[0] > 0` và `hist[255] > 0`. |
| **Khâu Gọi Provider trong Worker** | **Sự thật Thực nghiệm** | `backend/app/pipeline/worker.py:163-168` | Worker gọi `await self.bg_provider.remove_background(raw_bytes)` và lọc độc ngay bằng `self.sanitizer.sanitize_image(rgba_png_bytes)`. |
| **Ràng buộc Memory Pattern của DirectML** | **Sự thật Thực nghiệm** | Tài liệu chính thức Microsoft DirectML ONNX Runtime & mã nguồn EP | `DmlExecutionProvider` ném ngoại lệ runtime nếu `enable_mem_pattern = True`. Thiết lập `options.enable_mem_pattern = False` là bắt buộc. |
| **Không Tự Động Fallback khi Driver Lỗi** | **Sự thật Thực nghiệm** | Đặc tả kỹ thuật ONNX Runtime C++ Core | ONNX Runtime KHÔNG tự động rơi về CPU khi DirectML gặp lỗi shader compilation hoặc GPU crash; ứng dụng buộc phải tự bọc try-catch để khởi tạo lại session CPU. |
| **Dung lượng Tệp Trọng số (176,069,933 bytes)** | **Sự thật Thực nghiệm** | Đo kiểm trực tiếp tệp nhị phân HuggingFace & GitHub Rembg | Tệp `isnetis.onnx` có kích thước chính xác 176,069,933 bytes, SHA-256 bắt đầu bằng `f15622d8...`. |
| **Chất lượng Phân vùng AI Định lượng (IoU/Dice)** | **Chưa Xác định Thực nghiệm** | Cần xây dựng tập kiểm chuẩn kèm Ground-Truth Mask | Chưa có tập mặt nạ chuẩn $\alpha^*$ cho nhân vật anime; chất lượng bóc tách sợi tóc và trang phục hiện dựa trên đánh giá trực quan của cộng đồng nguồn mở. |
| **Bản chất Đầu ra (Logits vs. Xác suất)** | **Giả thuyết Thiết kế** | Khảo sát các bản export khác nhau trong cộng đồng | Một số bản export tích hợp sẵn tầng Sigmoid ở cuối đồ thị ONNX, một số bản chỉ xuất logits thô. Thiết kế hậu xử lý cần kiểm tra động dải giá trị để áp dụng Sigmoid linh hoạt. |
| **Hiệu quả Tinh chỉnh của Guided Filter** | **Giả thuyết Thiết kế** | Thử nghiệm lý thuyết trên OpenCV | Guided Filter giúp làm mịn viền tóc mai nhưng làm tăng 15–40 ms độ trễ suy luận. Cần kiểm nghiệm thực tế độ trễ trên máy tính người dùng trước khi kích hoạt mặc định. |

---

## 5. DỰ PHÒNG THIẾT BỊ, QUẢN TRỊ TÀI NGUYÊN & ĐỒNG THỜI (R2 GPU Fallback & R3 Benchmark Plan)

### 5.1 Chiến lược Phân tầng Thiết bị Thực thi (DirectML trên DirectX 12 -> CPU)
Môi trường triển khai trọng tâm của Project AIC là máy tính để bàn và laptop chạy Windows 10/11. Chiến lược phần cứng ưu tiên hàng đầu là:

$$\mathbf{DirectML\ (DirectX\ 12\ GPU)} \xrightarrow[\text{thất bại / không có}]{Tự\ động\ dự\ phòng} \mathbf{CPU\ (Đa\ luồng\ OpenMP\ ORT)}$$

#### Lợi thế Vượt trội Của DirectML:
- Không bị phụ thuộc vào hệ sinh thái độc quyền NVIDIA CUDA hay các gói cài đặt khổng lồ (cuDNN nặng hàng gigabyte).
- Hỗ trợ toàn diện và đồng nhất trên mọi dòng card đồ họa: **NVIDIA GeForce, AMD Radeon, Intel Arc, và cả đồ họa tích hợp Intel Iris Xe / AMD Radeon Graphics**.

### 5.2 Ràng buộc Cấu hình Bắt buộc Của DirectML (`enable_mem_pattern = False`)
ONNX Runtime yêu cầu thiết lập các cờ cấu hình `SessionOptions` cực kỳ nghiêm ngặt khi chạy DirectML:
- Với DirectML: **BẮT BUỘC** gán `options.enable_mem_pattern = False` và `options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL`. Nếu bật memory pattern optimization trên DirectML, trình điều khiển DirectX 12 sẽ ném ngoại lệ cấp phát bộ nhớ ngay lập tức.
- Với CPU: Cho phép gán `options.enable_mem_pattern = True` để tối ưu hóa việc tái sử dụng bộ đệm RAM hệ thống, cấu hình số luồng tính toán qua `options.intra_op_num_threads`.

### 5.3 Cô lập Lỗi Khởi tạo GPU Hai Giai đoạn (Hai tầng Try-Catch Phục hồi)
Quá trình khởi tạo GPU có thể gãy đổ ở hai thời điểm khác nhau:
1. Lúc tạo phiên (`InferenceSession`): Thiếu driver DirectX 12, thiết bị đồ họa bị khóa, hoặc môi trường headless thiếu subsystem đồ họa WDDM.
2. Lúc suy luận khởi động (`Warmup inference`): Shader DirectML biên dịch thất bại hoặc card đồ họa bị cạn kiệt VRAM cục bộ.

Nhà cung cấp ONNX cài đặt cơ chế cô lập lỗi 2 tầng:

```python
import asyncio
import gc
import io
import logging
from pathlib import Path
import time
from typing import Any

import numpy as np
import onnxruntime as ort
from PIL import Image

logger = logging.getLogger(__name__)


class OnnxBackgroundRemovalProvider(BackgroundRemovalProvider):

  def __init__(self, config: PipelineConfig) -> None:
    self.config = config
    self._session: ort.InferenceSession | None = None
    self._active_provider: str = "uninitialized"
    self._lock = asyncio.Lock()
    self._fallback_occurred: bool = False

  @property
  def model_name(self) -> str:
    return "isnet_anime"

  @property
  def execution_provider(self) -> str:
    return self._active_provider

  def _ensure_session_loaded(self) -> None:
    """Nạp phiên nếu chưa được khởi tạo hoặc sau khi đã giải phóng."""
    if self._session is None:
      self._init_session_sync()

  def _init_session_sync(self) -> None:
    """Khởi tạo phiên đồng bộ với thiết kế đề xuất cơ chế dự phòng hai tầng (chưa triển khai)."""
    model_file = Path(
        getattr(
            self.config, "isnet_anime_model_path", "data/models/isnet-anime.onnx"
        )
    )
    expected_sha = getattr(
        self.config,
        "isnet_anime_expected_sha256",
        "f15622d853e8260172812b657053460e20806f04b9e05147d49af7bed31a6e99",
    )

    # BẢO ĐẢM BẤT BIẾN PRE-LOAD: Xác minh mã băm SHA-256 dạng luồng trước khi nạp
    if getattr(self.config, "verify_model_hash", True):
      if not verify_model_sha256(model_file, expected_sha):
        raise ModelIntegrityError(
            f"Mã băm của tệp {model_file} không khớp giá trị kỳ vọng "
            f"({expected_sha}). Từ chối nạp mô hình."
        )

    model_path = str(model_file)
    available = ort.get_available_providers()
    enable_gpu = getattr(self.config, "enable_gpu", True)
    gpu_device_id = getattr(self.config, "gpu_device_id", 0)
    cpu_threads = getattr(self.config, "cpu_threads", 4)

    # TẦNG 1: Thử nghiệm DirectML
    if enable_gpu and "DmlExecutionProvider" in available:
      try:
        dml_opts = ort.SessionOptions()
        dml_opts.enable_mem_pattern = False  # BẮT BUỘC CHO DIRECTML
        dml_opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        dml_opts.graph_optimization_level = (
            ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        )

        providers = [
            ("DmlExecutionProvider", {"device_id": gpu_device_id}),
            "CPUExecutionProvider",
        ]
        session = ort.InferenceSession(
            model_path, dml_opts, providers=providers
        )

        # Chạy thử suy luận khởi động (Warmup) để ép biên dịch shader và kiểm tra VRAM
        dummy = np.zeros((1, 3, 1024, 1024), dtype=np.float32)
        in_name = session.get_inputs()[0].name
        session.run(None, {in_name: dummy})

        self._session = session
        self._active_provider = "directml"
        logger.info(
            "Khởi tạo thành công IS-Net Anime trên DirectML (Device: %d)",
            gpu_device_id,
        )
        return
      except Exception as exc:
        logger.warning(
            "DirectML gặp sự cố (%s: %s). Thử nghiệm hạ cấp sang CPU theo đề"
            " xuất thiết kế.",
            type(exc).__name__,
            str(exc),
        )
        self._fallback_occurred = True
        gc.collect()

    # TẦNG 2: Khởi tạo CPU Dự phòng
    cpu_opts = ort.SessionOptions()
    cpu_opts.enable_mem_pattern = True
    cpu_opts.intra_op_num_threads = cpu_threads
    cpu_opts.inter_op_num_threads = 1
    cpu_opts.graph_optimization_level = (
        ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    )

    self._session = ort.InferenceSession(
        model_path, cpu_opts, providers=["CPUExecutionProvider"]
    )
    self._active_provider = "cpu"
    logger.info(
        "Khởi tạo thành công IS-Net Anime trên CPU (Threads: %d)",
        cpu_threads,
    )

  def _run_inference_sync(
      self, image_bytes: bytes, **kwargs: Any
  ) -> tuple[bytes, dict[str, Any]]:
    """Thực thi toàn bộ chuỗi tiền xử lý, suy luận ONNX và hậu xử lý trên worker thread."""
    t0 = time.perf_counter()
    if self._session is None:
      raise RuntimeError("ONNX Session chưa được khởi tạo.")

    # 1. Đọc ảnh gốc qua Pillow
    orig_img = Image.open(io.BytesIO(image_bytes))
    w_orig, h_orig = orig_img.size

    # 2. Tiền xử lý đệm khung đối xứng letterbox -> [1, 3, 1024, 1024]
    input_tensor, pad_meta = preprocess_letterbox(orig_img)
    in_name = self._session.get_inputs()[0].name

    # 3. Chạy suy luận ONNX Runtime C++ (chặn luồng worker)
    out_tensors = self._session.run(None, {in_name: input_tensor})
    raw_mask = out_tensors[0]  # shape: [1, 1, 1024, 1024]

    # 4. Hậu xử lý unpad, sigmoid và tạo dải alpha mềm
    alpha_img = postprocess_mask(raw_mask, pad_meta, (w_orig, h_orig))

    # 5. Kiểm chuẩn 4 cổng chất lượng mặt nạ alpha với đầy đủ tham số hiệu chuẩn
    valid, err_msg, warnings = validate_alpha_matte(
        alpha_img,
        allow_translucent=kwargs.get("allow_translucent", False),
        allow_full_bleed=kwargs.get("allow_full_bleed", False),
        min_coverage=kwargs.get("min_coverage", 0.05),
        max_coverage=kwargs.get("max_coverage", 0.98),
        min_dimension=kwargs.get("min_dimension", None),
    )
    if not valid:
      raise ValueError(f"Kiểm chuẩn mặt nạ alpha thất bại: {err_msg}")

    # 6. Ghép RGBA an toàn qua putalpha
    rgb_img = orig_img.convert("RGB")
    rgba_img = rgb_img.copy()
    rgba_img.putalpha(alpha_img)

    buf = io.BytesIO()
    rgba_img.save(buf, format="PNG", optimize=True)
    out_png_bytes = buf.getvalue()

    latency_ms = (time.perf_counter() - t0) * 1000.0
    meta = {
        "model_name": self.model_name,
        "execution_provider": self.execution_provider,
        "device_id": (
            getattr(self.config, "gpu_device_id", 0)
            if self._active_provider == "directml"
            else None
        ),
        "fallback_occurred": self._fallback_occurred,
        "latency_ms": round(latency_ms, 2),
        "input_shape": [1, 3, 1024, 1024],
        "output_shape": list(raw_mask.shape),
        "alpha_extrema": list(alpha_img.getextrema() or (0, 0)),
        "warnings": warnings,
    }
    return out_png_bytes, meta
```

### 5.4 Ghi log Thiết bị Hoạt động và Metadata Chẩn đoán
Mỗi lần thực thi `remove_background()`, hệ thống trả về metadata cấu trúc minh bạch:
```json
{
  "model_name": "isnet_anime",
  "execution_provider": "directml",
  "device_id": 0,
  "fallback_occurred": false,
  "latency_ms": 235.6,
  "input_shape": [1, 3, 1024, 1024],
  "output_shape": [1, 1, 1024, 1024],
  "alpha_extrema": [0, 255]
}
```
Nhật ký Worker ghi nhận tường minh:
`INFO: Character 'miku' matting completed in 235.6ms via DirectML (fallback=False)`

### 5.5 Phân loại Số liệu Hiệu năng (Nhóm A / B / C) & Kế hoạch Benchmark DirectML trên RTX 4050 6GB

Nhằm duy trì tính trung thực tuyệt đối theo chế độ `Integrity Mode Development`, toàn bộ các số liệu hiệu năng và tài nguyên được phân loại rạch ròi thành 3 nhóm trạng thái:

| Nhóm Phân Loại | Định Nghĩa Tiêu Chuẩn | Các Chỉ Số / Tuyên Bố Kỹ Thuật Cụ Thể | Bằng Chứng / Phương Pháp Xác Minh |
|---|---|---|---|
| **Nhóm A: Thực nghiệm Đã Đo Kiểm Thực Tế (Actually Measured)** | Các số liệu đã được đo kiểm trực tiếp trên máy phát triển hoặc bộ kiểm thử tự động của Project AIC. | - Thời gian chạy test suite Pipeline Core cơ sở: **218/218 tests passing** (100% offline trên CPU, áp dụng riêng cho Pipeline Core với `MockBackgroundRemovalProvider`; **tuyệt đối KHÔNG chứng minh mô hình IS-Net thực tế hay DirectML hoạt động**).<br>- Kích thước tệp nhị phân trọng số: **176,069,933 bytes** (~176.07 MB).<br>- RAM nền cơ sở của Mock Provider: **~50 MB**.<br>- Sai số bảo toàn hình học đệm khung khứ hồi: **$\le 0.081\text{ px}$** trên 17 kích thước ảnh. | Nhật ký thực thi `pytest`, kiểm toán nhị phân SHA-256 tệp `isnetis.onnx`, và bài test hình học `test_normalizer_alignment.py`. |
| **Nhóm B: Ước Lượng Từ Lý Thuyết & Tài Liệu Kiến Trúc (Estimated from Literature/Architecture)** | Các số liệu suy diễn từ cấu trúc mạng nơ-ron IS-Net, đặc tả bộ đệm tensor ONNX Runtime, hoặc tài liệu công bố của các dự án tiền nhiệm (`rembg`, `anime-segmentation`). **(Ước lượng chưa đo kiểm thực tế)** | - Dung lượng VRAM đồ họa đỉnh khi suy luận $1024 \times 1024$: **ước tính ~750 MB – 1,100 MB** (tính từ: trọng số FP32 176 MB + tensor ảnh đầu vào NCHW 12.6 MB + bộ đệm kích hoạt trung gian đỉnh qua 6 tầng RSU Encoder-Decoder ~450 MB + workspace DirectML; đây là ước tính lý thuyết, chưa đo kiểm thực tế).<br>- Dung lượng RAM hệ thống khi chạy CPU: **ước tính ~300 MB – 700 MB**.<br>- Độ trễ suy luận trên CPU: **ước tính ~1.2s – 3.5s** (tùy số nhân CPU và số luồng OpenMP). | Tính toán kích thước ma trận tensor toán học và đối chiếu tài liệu kỹ thuật của Microsoft DirectML / ONNX Runtime C++ Core. |
| **Nhóm C: Giả Thuyết Chưa Được Kiểm Chứng Trên Môi Trường Mục Tiêu (Unverified Hypothesis)** | Các kỳ vọng kỹ thuật về phần cứng mục tiêu hoặc tính năng nâng cao chưa qua đo kiểm thực tế trong môi trường Windows với GPU NVIDIA RTX 4050. | - Độ trễ suy luận trên Windows với GPU NVIDIA RTX 4050 6GB qua DirectML: **ước tính/giả thuyết thiết kế ~0.2s (150–250 ms)** (hoàn toàn chưa kiểm chứng thực nghiệm).<br>- Thu hồi bộ nhớ VRAM sau khi gọi `release()`: **VRAM KHÔNG được giải phóng về đúng 0 MB ngay lập tức**. Do cơ chế memory pooling của trình điều khiển DirectX 12 và DirectML allocator, bộ nhớ đồ họa heap đã cấp phát thường được driver/OS duy trì cho tới khi tiến trình kết thúc. Do đó, tuyệt đối không tuyên bố VRAM được giải phóng về đúng 0 MB.<br>- Khả năng chuyển dịch sang CPU khi GPU bị OOM: **Đề xuất thiết kế kiến trúc chưa được lập trình hay kiểm thử trong codebase**; không bảo đảm mọi lỗi DirectML OOM/device errors đều có thể phục hồi an toàn. | Cần thực thi bộ benchmark chuyên biệt trên phần cứng thực tế trong giai đoạn triển khai Phase 0.5B để chuyển sang Nhóm A. |

> **CẢNH BÁO QUAN TRỌNG VỀ PHÂN ĐỊNH HIỆU NĂNG:**  
> 1. Kết quả **218 tests passing** của Nhóm A thuộc về bộ khung Pipeline Core chạy Mock Provider; **kết quả này KHÔNG chứng minh mô hình IS-Net thực tế hay provider DirectML đã hoạt động**.  
> 2. Tuyệt đối **KHÔNG ĐƯỢC PHÉP** trình bày các số liệu thuộc **Nhóm B** (Ước lượng lý thuyết) và **Nhóm C** (Giả thuyết thiết kế) như những kết quả thực nghiệm đã được kiểm chứng! Con số ~0.2s và dung lượng VRAM/RAM thuần túy là mục tiêu thiết kế và ước tính kiến trúc chưa qua đo kiểm.  
> 3. Tuyệt đối **KHÔNG TUYÊN BỐ VRAM được giải phóng về đúng 0 MB** sau khi gọi hàm `release()`.

#### Kế hoạch Benchmark DirectML Chuyên Biệt Trên Windows (NVIDIA RTX 4050 6GB):
Nhằm cung cấp bằng chứng thực nghiệm chính xác, một kịch bản đo kiểm chuẩn hóa được thiết kế riêng cho máy tính Windows trang bị card đồ họa **NVIDIA GeForce RTX 4050 Laptop GPU (6 GB GDDR6)**:
- **Cấu hình Môi trường:** Windows 11 64-bit, WDDM 3.1, DirectX 12 Feature Level 12_1, Python 3.12, gói `onnxruntime-directml>=1.19.0`.
- **8 Kịch bản Đo kiểm Thực tế (Benchmark Scenarios):**
  1. **Cold Load Latency (Độ trễ nạp nguội):** Đo thời gian đọc tệp 176 MB từ ổ cứng SSD NVMe, băm kiểm tra SHA-256 dạng luồng, khởi tạo `ort.InferenceSession` với `DmlExecutionProvider`.
  2. **Warm-up Latency (Độ trễ khởi động):** Đo thời gian chạy suy luận bức ảnh giả lập đầu tiên (thời gian biên dịch shader DirectX 12 và cấp phát bộ nhớ đồ họa khởi đầu).
  3. **Steady-State Inference Latency (Độ trễ suy luận ổn định):** Chạy liên tục 50 bức ảnh kích thước $1024 \times 1024$, ghi nhận phân phối độ trễ: Trung bình (Mean), Trung vị (Median), Bách phân vị P95 và P99 (ms).
  4. **Peak VRAM Usage (Bộ nhớ đồ họa đỉnh):** Đo thông qua NVML API (`pynvml`) và bộ đếm hiệu năng DirectX DXGI tại 4 mốc: Trước khi nạp, Sau warmup, Tại đỉnh suy luận ảnh phức tạp, và Sau khi kết thúc tác vụ.
  5. **System RAM Usage (Bộ nhớ RAM hệ thống):** Giám sát chỉ số Resident Set Size (RSS) của tiến trình worker qua `psutil` xuyên suốt các giai đoạn.
  6. **Sequential Image Processing (Xử lý chuỗi ảnh liên tục):** Xử lý tuần tự 20 ảnh sprite Miku liên tiếp, kiểm tra đồ thị bộ nhớ để phát hiện rò rỉ bộ nhớ (memory leaks) hoặc hiện tượng tích tụ bộ đệm DirectML.
  7. **Release and Reload Lifecycle (Vòng đời giải phóng và nạp lại):** Gọi `provider.release()`, đo lượng VRAM và RAM thực tế được hoàn trả cho hệ điều hành (lưu ý driver DirectX 12 có thể giữ lại bộ đệm heap, không cam kết giải phóng về 0 MB), sau đó gửi yêu cầu tách nền mới để kiểm tra tính năng tái khởi tạo phiên làm việc (lazy re-initialization).
  8. **DirectML Failure with CPU Fallback (Thử nghiệm ép lỗi DirectML và chuyển sang CPU):** Giả lập lỗi thiết bị phần cứng (truyền sai `device_id=999` hoặc tắt thiết bị DirectX 12), đo thời gian phát hiện lỗi, thời gian khởi tạo phiên CPU dự phòng và kiểm tra tính toàn vẹn của ảnh đầu ra (kiểm nghiệm tính khả thi của thiết kế phục hồi).

### 5.6 Vòng đời Phiên Thực thi, Khởi tạo Lười (Lazy Loading) và Kiểm soát Đồng thời
1. **Khởi tạo Lười (Lazy Initialization):** Quá trình nạp mô hình vào RAM và VRAM chỉ diễn ra khi có yêu cầu tách nền đầu tiên hoặc khi lệnh CLI warmup được gọi.
2. **Kiểm soát Đồng thời (Concurrency Governor):** Cấu hình `worker_concurrency = 1` bảo đảm xử lý tuần tự từng ảnh trong nền. Khóa bất đồng bộ `asyncio.Lock` trong provider ngăn chặn triệt để tình trạng hai coroutine cùng khởi tạo phiên đồng thời hoặc gửi lệnh song song vào DirectML gây xung đột tài nguyên đồ họa.
3. **Thực thi Bất đồng bộ Không Chặn Event Loop (Non-blocking Thread Offloading):** Hàm C++ `session.run()` của ONNX Runtime là tác vụ tính toán nặng (compute-bound) đồng bộ và chặn luồng (blocking). Để bảo đảm server FastAPI không bị đóng băng (không làm nghẽn các endpoint kiểm tra sức khỏe `/healthz` hay các tiến trình HTTP khác), phương thức bất đồng bộ `remove_background()` bắt buộc phải ủy thác hàm suy luận đồng bộ sang luồng riêng qua `await asyncio.to_thread(self._run_inference_sync, ...)`.
4. **Giải phóng Tài nguyên Phiên (`release()`):**
```python
def release(self) -> None:
  if self._session is not None:
    del self._session
    self._session = None
    self._active_provider = "released"
    gc.collect()
    logger.info(
        "Đã giải phóng tham chiếu phiên ONNX Runtime và yêu cầu thu dọn bộ"
        " nhớ."
    )
```
   *Lưu ý kỹ thuật về giải phóng bộ nhớ:* Thao tác `release()` hủy bỏ đối tượng session ONNX Runtime và gọi `gc.collect()` ở tầng Python. Tuy nhiên, theo đặc tả quản trị bộ nhớ của DirectX 12 và trình điều khiển WDDM, **VRAM đồ họa không được giải phóng về đúng 0 MB ngay lập tức** do driver duy trì bộ nhớ đệm (cached heap) để tái sử dụng. Ứng dụng không đưa ra cam kết giải phóng VRAM về 0 MB.

### 5.7 Đề Xuất Thiết Kế Cơ Chế Phục Hồi khi Tràn Bộ Nhớ Đồ Họa (Proposed GPU OOM to CPU Fallback - Chưa Triển Khai)

> **CẢNH BÁO KIẾN TRÚC & PHÂN ĐỊNH HIỆN TRẠNG (PROPOSAL ONLY):**  
> Cơ chế phục hồi 6 bước dưới đây là **ĐỀ XUẤT THIẾT KẾ KIẾN TRÚC (Architectural Proposal)** cho Phase 0.5B, **HOÀN TOÀN CHƯA ĐƯỢC TRIỂN KHAI HOẶC KIỂM CHỨNG TRONG CODEBASE HIỆN TẠI**.  
> Tuyệt đối không được hiểu hoặc khẳng định rằng hệ thống đã hoàn thiện tính năng chuyển sang CPU hoặc cam kết ứng dụng luôn hoạt động không gián đoạn. Thay vào đó, đây là đề xuất thiết kế kiến trúc sẽ được triển khai và kiểm thử thực nghiệm trong Phase 0.5B.  
> Ngoài ra, cơ chế này chỉ là nỗ lực phục hồi ở mức ứng dụng (best-effort recovery); **KHÔNG THỂ BẢO ĐẢM RẰNG MỌI LỖI DirectML OOM HAY LỖI THIẾT BỊ ĐỀU CÓ THỂ KHÔI PHỤC ĐƯỢC AN TOÀN**.

Trong môi trường runtime DirectML trên Windows:
- Khi card đồ họa bị cạn kiệt VRAM (ví dụ người dùng khởi chạy ứng dụng 3D nặng hoặc render video đồng thời trong lúc worker đang xử lý ảnh), trình điều khiển DirectX 12 sẽ từ chối cấp phát bộ nhớ GPU.
- Lỗi này được ném ra từ tầng C++ của ONNX Runtime dưới dạng **`ort.OrtException`** kèm các mã HRESULT DirectX:
  * `0x8007000e: E_OUTOFMEMORY` (Cạn kiệt bộ nhớ cấp phát GPU/DirectX).
  * `0x887A0005: DXGI_ERROR_DEVICE_REMOVED` (Thiết bị đồ họa bị ngắt hoặc driver bị reset bởi TDR).
  * `0x887A0006: DXGI_ERROR_DEVICE_HUNG` (Lệnh GPU bị treo quá thời gian cho phép).
- Sau khi xảy ra `DEVICE_REMOVED` hoặc GPU driver crash, phiên DirectML cũ (`_session`) hoàn toàn bị vô hiệu hóa.

#### Đề Xuất Thiết Kế 6 Bước Phục Hồi (Kế Hoạch Triển Khai & Kiểm Thử):
Khi bước vào giai đoạn lập trình Phase 0.5B, lớp `OnnxBackgroundRemovalProvider` được đề xuất sẽ triển khai quy trình 6 bước như sau:

```python
async def remove_background(
    self,
    image_bytes: bytes,
    **kwargs: Any,
) -> tuple[bytes, dict[str, Any]]:
  async with self._lock:
    self._ensure_session_loaded()

    try:
      # Thực thi suy luận trên provider hiện tại (DirectML nếu khả dụng), bảo toàn đầy đủ **kwargs
      return await asyncio.to_thread(
          self._run_inference_sync, image_bytes, **kwargs
      )
    except (ort.OrtException, RuntimeError) as exc:
      err_msg = str(exc)

      # BƯỚC 1: Bắt và phân loại ngoại lệ HRESULT DirectX (OOM / Device Removed / Device Hung)
      is_gpu_oom = any(
          marker in err_msg
          for marker in [
              "0x8007000e",
              "E_OUTOFMEMORY",
              "0x887A0005",
              "DXGI_ERROR_DEVICE_REMOVED",
              "DXGI_ERROR_DEVICE_HUNG",
              "DirectML device removed",
          ]
      )
      if not is_gpu_oom or self._active_provider == "cpu":
        # Nếu lỗi không phải do VRAM OOM hoặc đã là CPU thì ném tiếp
        raise

      logger.critical(
          "Phát hiện sự cố cạn kiệt VRAM GPU DirectML (%s). "
          "Kích hoạt đề xuất phục hồi: Hủy session GPU và tái khởi tạo CPU.",
          err_msg,
      )

      # BƯỚC 2: Hủy bỏ phiên DirectML bị tê liệt
      self._session = None

      # BƯỚC 3: Giải phóng tham chiếu Python và yêu cầu dọn dẹp bộ nhớ
      # LƯU Ý: gc.collect() chỉ giải phóng tham chiếu Python; KHÔNG bảo đảm driver GPU hoàn trả VRAM tức thì!
      gc.collect()

      # BƯỚC 4: Đề xuất khởi tạo phiên làm việc CPU mới với cấu hình an toàn
      # LƯU Ý: Bước này có thể thất bại nếu hệ thống cạn kiệt RAM vật lý (System OOM) hoặc tệp mô hình bị hỏng!
      cpu_threads = getattr(self.config, "cpu_threads", 4)
      model_path = str(
          getattr(
              self.config,
              "isnet_anime_model_path",
              "data/models/isnet-anime.onnx",
          )
      )
      cpu_opts = ort.SessionOptions()
      cpu_opts.enable_mem_pattern = True
      cpu_opts.intra_op_num_threads = cpu_threads
      cpu_opts.inter_op_num_threads = 1
      cpu_opts.graph_optimization_level = (
          ort.GraphOptimizationLevel.ORT_ENABLE_ALL
      )
      self._session = ort.InferenceSession(
          model_path,
          cpu_opts,
          providers=["CPUExecutionProvider"],
      )

      # BƯỚC 5: Chốt trạng thái (Latch) sang CPU để ngăn flapping giữa các tác vụ kế tiếp
      self._active_provider = "cpu"
      self._fallback_occurred = True

      # BƯỚC 6: Thử thực hiện lại tác vụ suy luận trên CPU và đính kèm siêu dữ liệu chẩn đoán
      # LƯU Ý: Bước suy luận lại cũng có thể thất bại nếu RAM không đủ cấp phát bộ đệm kích hoạt trung gian!
      logger.info(
          "Tái thực hiện suy luận cho ảnh hiện tại trên CPUExecutionProvider."
      )
      out_bytes, meta = await asyncio.to_thread(
          self._run_inference_sync, image_bytes, **kwargs
      )
      meta["fallback_occurred"] = True
      meta["fallback_reason"] = err_msg
      return out_bytes, meta
```

#### Phân Tích Các Giới Hạn và Rủi Ro Cốt Lõi Của Cơ Chế Dự Phòng:
1. **Lệnh `gc.collect()` không bảo đảm giải phóng VRAM ngay lập tức:** Trình điều khiển đồ họa DirectX 12 và hệ điều hành WDDM quản lý bộ nhớ VRAM theo cơ chế heap riêng biệt. Lệnh `gc.collect()` ở tầng Python chỉ hủy các đối tượng wrapper và giảm bộ đếm tham chiếu COM, nhưng driver có thể giữ lại bộ nhớ heap đó trong bộ đệm đồ họa. Do đó, không thể kỳ vọng VRAM được giải phóng lập tức hay giải phóng về đúng 0 MB.
2. **Khởi tạo phiên CPU hoặc suy luận lại vẫn có thể thất bại:** Tại Bước 4, việc nạp phiên ONNX Runtime trên CPU yêu cầu cấp phát thêm 300–700 MB RAM hệ thống. Nếu máy tính đang bị cạn kiệt RAM toàn cục (System OOM) hoặc tệp mô hình không thể đọc, việc khởi tạo CPU session sẽ ném ngoại lệ. Tương tự tại Bước 6, việc chạy lại suy luận trên CPU vẫn có thể thất bại nếu không đủ bộ nhớ cho các tensor trung gian.
3. **Không phải mọi lỗi DirectML đều có thể cứu được an toàn:** Các lỗi phần cứng nghiêm trọng như GPU Device Hung kích hoạt cơ chế Timeout Detection and Recovery (TDR) ở cấp nhân Windows, hoặc crash ở tầng kernel driver WDDM, có thể làm hệ điều hành vô hiệu hóa thiết bị đồ họa hoặc cưỡng chế dừng toàn bộ tiến trình ứng dụng (process crash). Đề xuất này là giải pháp giảm thiểu rủi ro khi gặp lỗi OOM thông thường, chứ không thể cam kết ngăn chặn hoàn toàn việc tiến trình bị dừng hoặc lỗi trong mọi tình huống.

### 5.8 Bảo tồn Tính Trừu tượng và Nhà cung cấp Giả lập Cho Môi trường CI
Mẫu thiết kế Factory (`create_background_provider(config)`) sẽ trả về:
- `MockBackgroundRemovalProvider` nếu `config.use_mock_bg_provider == True`.
- `OnnxBackgroundRemovalProvider` nếu `config.use_mock_bg_provider == False`.
Trong môi trường kiểm thử CI (GitHub Actions), cấu hình mặc định luôn là dùng Mock Provider, bảo đảm test suite chạy nhanh, nhẹ và không đòi hỏi GPU.

---

## 6. KẾ HOẠCH KIỂM THỬ ĐA TẦNG & CỔNG CHẤT LƯỢNG (R4 Multi-Tier Test Plan & Quality Gate)

Để bảo đảm chất lượng phần mềm đạt chuẩn kiểm toán nghiêm ngặt mà không làm chậm quy trình CI/CD hay đòi hỏi phần cứng đặc biệt, toàn bộ kiến trúc kiểm thử được phân định rạch ròi thành **4 Tầng Độc lập (4 Test Tiers)**:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                             MA TRẬN KẾ HOẠCH KIỂM THỬ 4 TẦNG (TEST TIERS)                        │
├────────────┬─────────────────────────────┬──────────────────────────────────┬────────────────────┤
│ Tầng       │ Phạm vi & Mục tiêu          │ Ràng buộc & Môi trường           │ Trạng thái Thực tế │
├────────────┼─────────────────────────────┼──────────────────────────────────┼────────────────────┤
│ **Tầng 1** │ Kiểm thử Đơn vị Mock        │ - Không nạp ONNX Runtime nặng    │ **ĐÃ CHẠY (RUN)**  │
│ (Mock CI)  │ - Tuân thủ Protocol         │ - 0 phụ thuộc mô hình học máy    │ 218/218 passed     │
│            │ - Kiểm tra cực trị alpha    │ - Chạy trên mọi OS & CI (Linux)  │ (KHÔNG kiểm chứng  │
│            │ - Điều phối 10 giai đoạn    │ - Thời gian: < 1 giây            │ IS-Net thực tế)    │
├────────────┼─────────────────────────────┼──────────────────────────────────┼────────────────────┤
│ **Tầng 2** │ Tích hợp CPU ONNX Nhân tạo  │ - Cài đặt gói onnxruntime cơ bản │ **CHƯA CHẠY**      │
│ (Synthetic)│ - Hợp đồng Tensor [1,3..]   │ - Mô hình ONNX siêu nhỏ ~2 KB    │ **(NOT RUN)**      │
│            │ - Padding / Unpadding       │ - 0 tải file 176 MB qua mạng     │ Kế hoạch đề xuất   │
│            │ - Khử Sigmoid, trích xuất A │ - Chạy trên GitHub Actions CPU   │ Phase 0.5B         │
│            │ - Tích hợp Worker toàn tuyến│ - Thời gian: < 2 giây            │                    │
├────────────┼─────────────────────────────┼──────────────────────────────────┼────────────────────┤
│ **Tầng 3** │ Tích hợp Trọng số Thực CPU  │ - Cần tệp isnet-anime.onnx thực  │ **CHƯA CHẠY**      │
│ (Real CPU) │ - Xác minh băm SHA-256 luồng│ - CPUExecutionProvider đa luồng  │ **(NOT RUN)**      │
│            │ - Kiểm tra ổn định số học   │ - Tự động SKIP nếu thiếu file    │ Kế hoạch đề xuất   │
│            │ - Định dạng tensor thực tế  │ - Thời gian: ~1.5 - 3.5 giây/ảnh │ Phase 0.5B         │
├────────────┼─────────────────────────────┼──────────────────────────────────┼────────────────────┤
│ **Tầng 4** │ Kiểm thử Phần cứng DirectML │ - Hệ điều hành Windows 10/11     │ **CHƯA CHẠY**      │
│ (DirectML) │ - Khởi tạo DirectX 12 EP    │ - GPU NVIDIA / AMD DirectX 12    │ **(NOT RUN)**      │
│            │ - Warmup shader compilation │ - Đánh dấu @pytest.mark.directml │ Kế hoạch đề xuất   │
│            │ - Đo độ trễ suy luận GPU    │ - Thử nghiệm ép lỗi hạ cấp CPU   │ Phase 0.5B         │
└────────────┴─────────────────────────────┴──────────────────────────────────┴────────────────────┘
```

### 6.1 Tầng 1: Kiểm thử Đơn vị với Mock Provider (Trạng thái: ĐÃ CHẠY & VƯỢT QUA - RUN)
- **Mã kiểm thử hiện hữu:** `backend/tests/pipeline/test_mock_background.py`, `test_pipeline_contracts.py`, `test_queue_and_worker.py`.
- **Môi trường:** Chạy 100% offline trên mọi nền tảng (Linux, macOS, Windows) trong luồng GitHub Actions CI.
- **Kết quả nghiệm thu:** Đã chạy thực tế, **218/218 bài kiểm thử vượt qua (37.04s)**.
- **Phạm vi bảo đảm:** Xác thực hợp đồng Protocol `BackgroundRemovalProvider`, cực trị alpha `final_alpha.getextrema() == (0, 255)`, dải histogram làm mịn biên, và tính nguyên tử của luồng xử lý 10 giai đoạn trong `PipelineWorker`.

> **CẢNH BÁO QUAN TRỌNG VỀ PHẠM VI TẦNG 1 (TIER 1 SCOPE BOUNDARY):**  
> Việc 218/218 bài kiểm thử Tầng 1 vượt qua thành công **chỉ chứng minh tính đúng đắn của luồng điều phối Pipeline Core và Mock Provider**.  
> **TẦNG 1 HOÀN TOÀN KHÔNG XÁC THỰC SUY LUẬN MÔ HÌNH IS-NET THỰC TẾ (Tier 1 does NOT validate real IS-Net inference)** cũng như không chứng minh được tính tương thích của ONNX Runtime hay DirectML trong hệ thống.

### 6.2 Tầng 2: Kiểm thử Tích hợp CPU ONNX với Mô hình Nhân tạo 2KB (Trạng thái: CHƯA CHẠY - NOT RUN)
- **Tệp kiểm thử kế hoạch:** `backend/tests/pipeline/test_onnx_provider_cpu.py`.
- **Sáng kiến Kỹ thuật Tách biệt:** Tạo một fixture sinh ra **mô hình ONNX nhân tạo hợp lệ nặng chỉ ~2 KB** ngay trong bộ nhớ tạm:
```python
@pytest.fixture(scope="session")
def synthetic_isnet_onnx(tmp_path_factory) -> Path:
  """Tạo mô hình ONNX siêu nhỏ (2KB) khớp đúng hợp đồng [1,3,1024,1024] -> [1,1,1024,1024]."""
  import onnx
  from onnx import TensorProto, helper

  model_path = tmp_path_factory.mktemp("models") / "synthetic_isnet.onnx"
  X = helper.make_tensor_value_info(
      "img", TensorProto.FLOAT, [1, 3, 1024, 1024]
  )
  Y = helper.make_tensor_value_info(
      "mask", TensorProto.FLOAT, [1, 1, 1024, 1024]
  )

  # Lớp tích chập 1x1 tính giá trị trung bình 3 kênh màu mô phỏng xác suất nền
  w = helper.make_tensor(
      "w", TensorProto.FLOAT, [1, 3, 1, 1], [0.333, 0.333, 0.333]
  )
  conv = helper.make_node(
      "Conv", inputs=["img", "w"], outputs=["conv_out"]
  )
  sig = helper.make_node(
      "Sigmoid", inputs=["conv_out"], outputs=["mask"]
  )

  graph = helper.make_graph(
      [conv, sig], "synthetic_isnet", [X], [Y], [w]
  )
  model = helper.make_model(graph, producer_name="aic-synthetic")
  onnx.save(model, str(model_path))
  return model_path
```

*Lưu ý về phụ thuộc kiểm thử:* Fixture sinh mô hình nhân tạo sử dụng thư viện `onnx` (trình biên dịch protobuf đồ thị ONNX). Do đó, giai đoạn 0.5B cần khai báo `onnx` trong nhóm phụ thuộc kiểm thử (`dev-dependencies`) trong `backend/pyproject.toml`, HOẶC lưu trữ sẵn tệp nhị phân fixture siêu nhẹ ~2 KB này tại `backend/tests/fixtures/synthetic_isnet.onnx` để bộ kiểm thử Tầng 2 trên CI có thể chạy thuần túy với gói `onnxruntime` mà không cần cài thêm `onnx`.

> **CẢNH BÁO PHƯƠNG PHÁP LUẬN BẮT BUỘC VỀ TẦNG 2:**  
> Mô hình ONNX nhân tạo 2 KB **CHỈ ĐƯỢC THIẾT KẾ ĐỂ KIỂM CHỨNG TÍNH HỢP LỆ CỦA LỚP ADAPTER, HỢP ĐỒNG TENSOR VÀ QUY TRÌNH TÍCH HỢP PIPELINE** (kiểm tra tiền xử lý letterbox đối xứng, unpadding khôi phục tọa độ gốc, khử logits qua Sigmoid, trích xuất dải alpha mềm và chuyển giao dữ liệu cho `PipelineWorker`).  
> **MÔ HÌNH NHÂN TẠO 2 KB HOÀN TOÀN KHÔNG CHỨNG MINH ĐƯỢC HOẠT ĐỘNG CỦA MÔ HÌNH THỰC TẾ IS-NET CŨNG NHƯ KHÔNG PHẢN ÁNH CHẤT LƯỢNG PHÂN VÙNG AI**. Không được nhầm lẫn giữa việc pass Tầng 2 với việc mô hình AI đã bóc nền anime đạt yêu cầu.

### 6.3 Tầng 3: Kiểm thử Tích hợp Mô hình Thực IS-Net trên CPU (Trạng thái: CHƯA CHẠY - NOT RUN)
- **Tệp kiểm thử kế hoạch:** `backend/tests/pipeline/test_onnx_real_cpu.py`.
- **Phạm vi kiểm chứng:**
  1. Kiểm tra thuật toán băm SHA-256 dạng luồng trên tệp nhị phân thực tế 176 MB (`isnetis.onnx`).
  2. Nạp phiên `ort.InferenceSession` với `providers=['CPUExecutionProvider']` và tùy chọn `enable_mem_pattern=True`.
  3. Kiểm tra tính ổn định số học (không tràn số NaN, không crash bộ nhớ) khi chạy ảnh kích thước thực.
  4. Xác nhận dải giá trị tensor đầu ra thực tế khớp định dạng xác suất.
- **Điều kiện thực thi:** Tự động phát hiện tệp mô hình cục bộ (`data/models/isnet-anime.onnx`); nếu môi trường thiếu tệp (như trên GitHub Actions CI mặc định), bài kiểm thử tự động ghi nhận trạng thái SKIP an toàn.

### 6.4 Tầng 4: Kiểm thử Phần cứng DirectML GPU trên Windows (Trạng thái: CHƯA CHẠY - NOT RUN)
- **Tệp kiểm thử kế hoạch:** `backend/tests/pipeline/test_onnx_provider_directml.py`.
- **Cơ chế Gated Hardware:** Tự động bỏ qua nếu không phát hiện runtime DirectML trên máy tính:
```python
import onnxruntime as ort
import pytest

has_directml = (
    hasattr(ort, "get_available_providers")
    and "DmlExecutionProvider" in ort.get_available_providers()
)
pytestmark = pytest.mark.skipif(
    not has_directml,
    reason="Bỏ qua vì hệ thống không có phần cứng đồ họa DirectML",
)
```
- **Phạm vi kiểm chứng:**
  1. Khởi tạo phiên DirectML thực tế trên Windows với `enable_mem_pattern=False`.
  2. Đo thời gian biên dịch shader DirectML trong bước suy luận khởi động (warm-up inference).
  3. Đo độ trễ suy luận ổn định và mức chiếm dụng VRAM đỉnh trên GPU NVIDIA GeForce RTX 4050 6GB.
  4. Kiểm thử tình huống giả lập thiết bị lỗi (`device_id=999`) để kiểm nghiệm tính khả thi của đề xuất cơ chế try-catch hạ cấp về `CPUExecutionProvider` (lưu ý đây là đề xuất sẽ kiểm thử, không bảo đảm mọi lỗi phần cứng hay driver đều khôi phục được).

---

## 7. RỦI RO KỸ THUẬT, CÁC CHẾ ĐỘ THẤT BẠI & BIỆN PHÁP GIẢM THIỂU

| STT | Rủi ro Kỹ thuật / Chế độ Thất bại | Mức độ Nghiêm trọng | Xác suất | Giải pháp Giảm thiểu Kiến trúc (Mitigation Strategy) |
|---|---|---|---|---|
| 1 | **Rủi ro Pháp lý Bản quyền Bộ dữ liệu DIS5K** | Trung bình | Thấp | Áp dụng chiến lược **BYOM (Bring-Your-Own-Model)**; không lưu trữ file nhị phân trong mã nguồn Git; duy trì giao diện mở sẵn sàng tích hợp các mô hình thương mại (BRIA RMBG). *Lưu ý:* BYOM không xóa bỏ mọi rủi ro bản quyền; việc phân phối thương mại bắt buộc phải có đánh giá pháp lý độc lập phù hợp. |
| 2 | **Lỗi Trình điều khiển GPU DirectML (Driver Crash)** | Cao | Trung bình | Đề xuất thiết kế cơ chế bọc lỗi 2 tầng: bắt ngoại lệ khởi tạo/warmup để chuyển sang CPU; lưu ý lỗi nghiêm trọng/TDR reset ở cấp hệ điều hành vẫn có thể gây dừng tiến trình. |
| 3 | **Cạn kiệt Bộ nhớ Đồ họa Đột ngột (GPU VRAM OOM)** | Cao | Thấp | Đề xuất thiết kế 6 bước bắt ngoại lệ OOM, hủy session và thử tái khởi tạo trên CPU (lưu ý `gc.collect()` không bảo đảm giải phóng VRAM ngay, và tạo phiên CPU vẫn có thể thất bại nếu cạn RAM hệ thống). |
| 4 | **Biến dạng Tỷ lệ Giải phẫu Nhân vật Miku** | Cao | Cao nếu làm sai | Bắt buộc sử dụng thuật toán **Symmetrical Letterboxing**, cấm kéo dãn ảnh trực tiếp; unpad nội suy song tuyến trở lại kích thước gốc. |
| 5 | **Nhiễm Độc Chuỗi Cung ứng (Supply Chain Hijack)** | Rất cao | Thấp | Bắt buộc thực thi **Pre-Load Invariant**: kiểm tra mã băm SHA-256 dạng luồng trước khi nạp; cách ly tệp hỏng sang `quarantine/`; cấm tự động tải khi import. |
| 6 | **Rớt Mạng Khi Tải Trọng số Mô hình** | Trung bình | Trung bình | Tải qua file tạm `.tmp.<uuid>`, kiểm tra tính toàn vẹn SHA-256 và kích thước $176\text{MB}$ trước khi hoán đổi tên nguyên tử bằng `os.replace()`. |

---

## 8. DANH MỤC TỆP DỰ KIẾN, LỘ TRÌNH TRIỂN KHAI & XÁC MINH GIT REMOTE (R6 Git & Scope Restrictions)

Khi Owner chính thức hoàn tất xem xét và đưa ra quyết định đối với báo cáo khảo sát kiến trúc này, giai đoạn triển khai mã nguồn tiếp theo của Phase 0.5B sẽ tiến hành các thay đổi độc lập và an toàn như sau:

### 8.1 Danh mục Tệp Dự kiến
1. `backend/pyproject.toml` (Sửa đổi): Bổ sung phụ thuộc `onnxruntime-directml>=1.19.0` (cho Windows) hoặc `onnxruntime>=1.19.0` (cho Linux CI); bổ sung `onnx` vào nhóm `dev-dependencies` phục vụ fixture kiểm thử Tầng 2 (hoặc đóng gói sẵn tệp nhị phân fixture 2 KB).
2. `backend/app/pipeline/config.py` (Sửa đổi): Bổ sung các thiết lập cấu hình đường dẫn `isnet_anime_model_path`, mã băm kỳ vọng, cờ kích hoạt GPU, và `use_mock_bg_provider`.
3. `backend/app/pipeline/background/image_ops.py` (Tạo mới): Chứa các hàm toán học thuần túy xử lý letterbox, unpad, sigmoid và 4 cổng kiểm định mặt nạ alpha.
4. `backend/app/pipeline/background/isnet_provider.py` (Tạo mới): Triển khai lớp `OnnxBackgroundRemovalProvider` tuân thủ Protocol `BackgroundRemovalProvider`.
5. `backend/app/pipeline/background/factory.py` (Tạo mới): Chứa hàm nhà xưởng `create_background_provider(config)`.
6. `backend/app/pipeline/security/model_verifier.py` (Tạo mới): Chứa hàm xác thực mã băm SHA-256 dạng luồng và cơ chế cách ly tệp hỏng.
7. `backend/app/cli/pipeline.py` (Tạo mới): Lệnh CLI tải mô hình ngoài luồng an toàn.
8. `backend/tests/pipeline/test_onnx_provider_cpu.py` (Tạo mới): Bộ kiểm thử Tầng 2 với fixture mô hình nhân tạo 2KB trên CPU.
9. `backend/tests/pipeline/test_onnx_real_cpu.py` (Tạo mới): Bộ kiểm thử Tầng 3 với trọng số thực IS-Net trên CPU.
10. `backend/tests/pipeline/test_onnx_provider_directml.py` (Tạo mới): Bộ kiểm thử Tầng 4 trên phần cứng DirectML GPU.

### 8.2 Lộ trình Triển khai Đề xuất
- **Bước 1:** Bổ sung cấu hình và hàm toán học xử lý hình ảnh (`image_ops.py`).
- **Bước 2:** Xây dựng bộ xác thực mật mã SHA-256 và cô lập tệp hỏng (`model_verifier.py`).
- **Bước 3:** Triển khai `OnnxBackgroundRemovalProvider` với cơ chế DirectML + CPU fallback và factory pattern.
- **Bước 4:** Xây dựng bộ kiểm thử tích hợp Tầng 2 (CPU ONNX Synthetic 2KB), Tầng 3 (Real IS-Net CPU) và Tầng 4 (DirectML GPU).
- **Bước 5:** Tích hợp truyền metadata mô hình vào `PipelineWorker`, chạy toàn bộ 218+ tests bảo đảm không có hồi quy và mở PR nghiệm thu.

### 8.3 Xác minh Git Remote & Khẳng định Giới hạn Phạm vi (R6 Git & Scope Restrictions)

Nhằm phục vụ công tác thanh tra, kiểm toán độc lập của Owner và hệ thống GitHub connector:

#### 1. Thông Tin Định Danh Nhánh & Commit Git:
- **Tên nhánh khảo sát kiến trúc:** `docs/m0-task-05b-architecture-survey` (phân nhánh từ `main`).
- **Kho lưu trữ từ xa (Remote Origin):** `https://github.com/nguyenphanminhkhanh9a-netizen/Project-AIC.git`
- **Đường dẫn nhánh trên GitHub:**  
  [`https://github.com/nguyenphanminhkhanh9a-netizen/Project-AIC/tree/docs/m0-task-05b-architecture-survey`](https://github.com/nguyenphanminhkhanh9a-netizen/Project-AIC/tree/docs/m0-task-05b-architecture-survey)
- **Commit cơ sở từ PR #5:** `fb5b21f0fa59ddc4983d29f1500f5672d3b7205e` (Merge PR #5 — Pipeline Core Phase 0.5A).
- **Commit khảo sát ban đầu trên remote:** `8b92a2b821a4844925640c184ca7570736053151`
- **Đường dẫn Commit khảo sát ban đầu trên GitHub:**  
  [`https://github.com/nguyenphanminhkhanh9a-netizen/Project-AIC/commit/8b92a2b821a4844925640c184ca7570736053151`](https://github.com/nguyenphanminhkhanh9a-netizen/Project-AIC/commit/8b92a2b821a4844925640c184ca7570736053151)
- **Commit hiệu đính & kiểm chứng thực nghiệm R1:** `0f9160c99823ce025738c30c70ca81280020cc8e`
- **Đường dẫn Commit hiệu đính R1 trên GitHub:**  
  [`https://github.com/nguyenphanminhkhanh9a-netizen/Project-AIC/commit/0f9160c99823ce025738c30c70ca81280020cc8e`](https://github.com/nguyenphanminhkhanh9a-netizen/Project-AIC/commit/0f9160c99823ce025738c30c70ca81280020cc8e)
- **Commit kiểm toán đối kháng Cycle 1 Reviewer R1:** `f8590bd97b17678aac2c05699b179711a485c06b`
- **Đường dẫn Commit Cycle 1 Reviewer R1 trên GitHub:**  
  [`https://github.com/nguyenphanminhkhanh9a-netizen/Project-AIC/commit/f8590bd97b17678aac2c05699b179711a485c06b`](https://github.com/nguyenphanminhkhanh9a-netizen/Project-AIC/commit/f8590bd97b17678aac2c05699b179711a485c06b)
- **Commit kiểm toán đối kháng Cycle 1 Reviewer R2:** `7949c0afe55c7c504689fc2e44d00ccf829a709f`
- **Đường dẫn Commit Cycle 1 Reviewer R2 trên GitHub:**  
  [`https://github.com/nguyenphanminhkhanh9a-netizen/Project-AIC/commit/7949c0afe55c7c504689fc2e44d00ccf829a709f`](https://github.com/nguyenphanminhkhanh9a-netizen/Project-AIC/commit/7949c0afe55c7c504689fc2e44d00ccf829a709f)
- **Commit kiểm toán đối kháng Cycle 1 Reviewer R3:** `5c343418dee88169583d76bdded1792b8dc844d6`
- **Đường dẫn Commit Cycle 1 Reviewer R3 trên GitHub:**  
  [`https://github.com/nguyenphanminhkhanh9a-netizen/Project-AIC/commit/5c343418dee88169583d76bdded1792b8dc844d6`](https://github.com/nguyenphanminhkhanh9a-netizen/Project-AIC/commit/5c343418dee88169583d76bdded1792b8dc844d6)
- **Commit hiệu đính Implementer:** `1ffeb67bd6da24d2155169621d01d35050befdc3`
- **Đường dẫn Commit Implementer trên GitHub:**  
  [`https://github.com/nguyenphanminhkhanh9a-netizen/Project-AIC/commit/1ffeb67bd6da24d2155169621d01d35050befdc3`](https://github.com/nguyenphanminhkhanh9a-netizen/Project-AIC/commit/1ffeb67bd6da24d2155169621d01d35050befdc3)
- **Commit kiểm toán đối kháng Reviewer R1:** `8700382693f447d296258e021b8a989f59a22fc6`
- **Đường dẫn Commit Reviewer R1 trên GitHub:**  
  [`https://github.com/nguyenphanminhkhanh9a-netizen/Project-AIC/commit/8700382693f447d296258e021b8a989f59a22fc6`](https://github.com/nguyenphanminhkhanh9a-netizen/Project-AIC/commit/8700382693f447d296258e021b8a989f59a22fc6)
- **Đường dẫn tệp báo cáo trực tiếp trên GitHub:**  
  [`https://github.com/nguyenphanminhkhanh9a-netizen/Project-AIC/blob/docs/m0-task-05b-architecture-survey/docs/architecture/phase-05b-isnet-anime-survey.md`](https://github.com/nguyenphanminhkhanh9a-netizen/Project-AIC/blob/docs/m0-task-05b-architecture-survey/docs/architecture/phase-05b-isnet-anime-survey.md)

#### 2. Lệnh Kiểm Tra Tính Toàn Vẹn Git:
```powershell
# 1. Kiểm tra nhánh hiện tại
git branch --show-current
# Kết quả kỳ vọng: docs/m0-task-05b-architecture-survey

# 2. Kiểm tra commit SHA
git rev-parse HEAD

# 3. Kiểm tra thống kê thay đổi so với main
git diff origin/main...HEAD --stat
# Kết quả kỳ vọng: DUY NHẤT 1 tệp docs/architecture/phase-05b-isnet-anime-survey.md thay đổi
```

#### 3. Cam kết Giới hạn Phạm vi Tuyệt đối (Scope Guardrails):
- **Zero Modification:** Cam kết **100% KHÔNG CÓ BẤT KỲ THAY ĐỔI NÀO** đối với mã nguồn ứng dụng (`backend/app/`), mã kiểm thử hiện hữu (`backend/tests/`), tệp cấu hình phụ thuộc (`backend/pyproject.toml`, `uv.lock`) hay các tệp cấu hình dự án.
- **Không Tự Động Merge:** Tuyệt đối không thực hiện thao tác git merge vào nhánh `main` và không kích hoạt chế độ auto-merge trên GitHub PR; mọi quyền quyết định nghiệm thu và sáp nhập thuộc về Project Owner.

---

## 9. TÓM TẮT DỄ HIỂU DÀNH CHO SẾP (R5 Plain Language Summary for Owner)

*(Báo cáo tóm lược tuân thủ Quy định Thư ký Dự án tại `AGENTS.md`, bảo đảm tính trung thực kỹ thuật và phân định rõ ràng giữa thiết kế lý thuyết và kết quả thực tế)*

Kính gửi Sếp, Thư ký Dự án xin được tóm tắt ngắn gọn toàn bộ hiện trạng báo cáo khảo sát kỹ thuật Phase 0.5B đợt này bằng ngôn ngữ đời thường, trực quan nhất:

- **1. Đã làm xong món gì mới? (Những gì đã được thiết kế và ghi nhận trong tài liệu):**  
  Em và đội ngũ đã hoàn thiện toàn diện bản thiết kế kiến trúc kỹ thuật để chuẩn bị nâng cấp cho Miku một **"cặp kính AI tách nền chuyên nghiệp"** (mô hình IS-Net Anime). Bản thiết kế đã xây dựng đầy đủ "khuôn đệm ảnh" (letterboxing) để không làm méo hình Miku, cơ chế "dải viền mờ mềm" (soft alpha) với mục tiêu hướng tới việc giữ các chi tiết sợi tóc mai và phụ kiện mỏng, "ổ khóa kiểm tra vân tay số" (SHA-256 dạng luồng) chống tráo đổi file, và 4 cổng kiểm tra chất lượng mặt nạ đầu ra. Xin lưu ý: Toàn bộ những nội dung này hiện **thuần túy nằm trong tài liệu khảo sát kỹ thuật**, chưa hề sửa đổi hay thêm bớt bất kỳ dòng code chương trình nào.

- **2. Nó hoạt động trên máy thế nào? (Những gì đã thực sự được kiểm tra):**  
  Thực tế kiểm tra cho thấy: Bộ khung sườn hiện tại của hệ thống (Pipeline Core Task 0.5A) vẫn đang chạy rất nhẹ và mượt mà, **vượt qua toàn bộ 218 bài kiểm tra tự động cũ** với bộ tách nền giả lập (Mock Provider). Phép thử toán học trên khung hình cũng khẳng định thuật toán co dãn không bị sai lệch (sai số dưới 0,081 pixel). Tuy nhiên, **218 bài test này chỉ chứng minh khung sườn ứng dụng chạy tốt, hoàn toàn CHƯA kiểm chứng mô hình AI IS-Net thật hay card đồ họa DirectML**.

- **3. Đã kiểm tra an toàn chưa? (Những gì còn chưa triển khai và chưa được kiểm chứng):**  
  Đội ngũ cam kết trung thực tuyệt đối, không gian lận, báo cáo rõ các điểm còn chưa làm và chưa kiểm chứng:  
  - *Chưa viết mã adapter AI:* Mã nguồn kết nối mô hình ONNX Runtime (`OnnxBackgroundRemovalProvider`) chưa được lập trình vào codebase.  
  - *Chưa chạy test mô hình thật:* Các tầng kiểm thử với mô hình giả lập ONNX (Tầng 2), mô hình thật trên CPU (Tầng 3), và mô hình thật trên card đồ họa DirectML (Tầng 4) đều đang ở trạng thái **CHƯA CHẠY (NOT RUN)**.  
  - *Hiệu năng và bộ nhớ mới là ước tính:* Con số tốc độ ~0,2 giây và mức tốn ~1 GB VRAM chỉ là ước tính lý thuyết và mục tiêu thiết kế trên giấy, chưa có số liệu đo đạc thực tế; đồng thời bộ nhớ đồ họa VRAM cũng không thể giải phóng ngay lập tức về 0 MB do cơ chế giữ bộ đệm của driver hệ điều hành.  
  - *Dự phòng CPU chỉ mới là đề xuất thiết kế:* Cơ chế 6 bước chuyển từ card đồ họa sang CPU khi tràn bộ nhớ mới là đề xuất trên bản vẽ, chưa được lập trình hay kiểm thử; trong thực tế không phải lỗi card đồ họa nào cũng cứu được, và việc tạo phiên CPU hay chạy lại cũng có thể lỗi nếu máy tính bị cạn sạch RAM.  
  - *Về bản quyền:* Tác giả mô hình đã gắn nhãn Apache-2.0 và dữ liệu DIS5K không tự động lây nhiễm lên trọng số, nhưng cơ chế BYOM không xóa bỏ hết mọi rủi ro; việc phân phối thương mại sau này vẫn cần có tư vấn pháp lý chuyên nghiệp độc lập.

- **4. Bước tiếp theo Sếp cần làm gì? (Quyết định tiếp theo của Sếp):**  
  Bản báo cáo khảo sát kiến trúc này đã được hiệu đính chuẩn xác và đẩy lên nhánh `docs/m0-task-05b-architecture-survey` trên GitHub để phục vụ việc lưu vết và kiểm toán độc lập. Thư ký xin kính trình bản báo cáo hiệu đính hoàn chỉnh này để Sếp xem xét và quyết định xem định hướng kiến trúc đề xuất (tích hợp IS-Net Anime với DirectML/CPU fallback và kế hoạch đo kiểm thực nghiệm) đã đủ chặt chẽ để đưa vào kế hoạch triển khai cho Phase 0.5B hay cần điều chỉnh thêm.
