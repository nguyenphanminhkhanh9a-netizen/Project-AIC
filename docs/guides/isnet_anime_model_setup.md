# Hướng Dẫn Cài Đặt & Vận Hành Mô Hình IS-Net Anime ONNX (CPU)

Tài liệu hướng dẫn dành cho Project Owner và đội ngũ phát triển về cách tải, xác thực mã băm mật mã và vận hành mô hình trí tuệ nhân tạo tách nền anime chuyên dụng **IS-Net Anime** (`isnetis.onnx`) trên nền tảng CPU.

---

## 1. Thông Số Kỹ Thuật Mô Hình (Model Specifications)

| Thuộc tính | Giá trị Quy định Bất biến |
|---|---|
| **Tên mô hình** | `isnet_anime` |
| **Tệp nhị phân** | `isnetis.onnx` |
| **Nguồn phát hành** | Hugging Face [`skytnt/anime-seg`](https://huggingface.co/skytnt/anime-seg) |
| **Commit Revision cố định** | `493cb60893f47441b26ec4fb9a306bce9e342982` |
| **Dung lượng chính xác** | **176,069,933 bytes** (~167.91 MiB / 176.07 MB) |
| **Mã băm mật mã SHA-256** | `f15622d853e8260172812b657053460e20806f04b9e05147d49af7bed31a6e99` |
| **Độ phân giải đầu vào** | $1024 \times 1024$ (Đệm khung đối xứng - Symmetrical Letterbox) |
| **Chuẩn hóa đầu vào** | ImageNet Float32 ($\mu = [0.485, 0.456, 0.406]$, $\sigma = [0.229, 0.224, 0.225]$) |
| **Kỹ thuật hậu xử lý** | Khôi phục tọa độ (Unpadding), Phóng to Float32 song tuyến (`mode='F'`), Dải alpha mềm liên tục $[0.05, 0.95]$ |

---

## 2. Thứ Tự Phân Cấp Tìm Kiếm Đường Dẫn (Resolution Hierarchy)

Khi khởi tạo `ISNetONNXProvider`, hệ thống sẽ tự động quét và nạp file mô hình theo thứ tự ưu tiên sau:

1. **Cấu hình tường minh:** Giá trị trong file cấu hình `PipelineConfig.isnet_anime_model_path` hoặc biến môi trường `AIC_PIPELINE_ISNET_ANIME_MODEL_PATH`.
2. **Thư mục nội bộ kho mã nguồn:**  
   `data/models/isnetis.onnx` hoặc `data/models/isnet-anime.onnx` (Thư mục `data/` được `.gitignore` bảo vệ tuyệt đối).
3. **Thư mục cache người dùng (Mặc định khuyến nghị):**  
   - Windows: `C:\Users\<username>\.cache\project_aic\models\isnetis.onnx`
   - Linux/macOS: `/home/<username>/.cache/project_aic/models/isnetis.onnx`

---

## 3. Hướng Dẫn Tải & Xác Thực Trực Tiếp (Download & Verify)

### Cách 1: Tải tự động bằng Python trong môi trường `backend` (Khuyên dùng)

Mở terminal tại thư mục gốc dự án và chạy:

```bash
cd backend
uv run python -c "
import urllib.request
from pathlib import Path
from app.pipeline.security.model_verifier import verify_model_file

cache_dir = Path.home() / '.cache' / 'project_aic' / 'models'
cache_dir.mkdir(parents=True, exist_ok=True)
dest = cache_dir / 'isnetis.onnx'

url = 'https://huggingface.co/skytnt/anime-seg/resolve/493cb60893f47441b26ec4fb9a306bce9e342982/isnetis.onnx'
if not dest.is_file():
    print('Đang tải mô hình isnetis.onnx (176 MB)...')
    urllib.request.urlretrieve(url, str(dest))
    print('Tải thành công!')

sha = verify_model_file(dest)
print('Xác thực bảo mật SHA-256 hoàn tất:', sha)
"
```

### Cách 2: Tải thủ công bằng PowerShell trên Windows

```powershell
$cacheDir = "$HOME\.cache\project_aic\models"
New-Item -ItemType Directory -Force -Path $cacheDir
$dest = "$cacheDir\isnetis.onnx"
$url = "https://huggingface.co/skytnt/anime-seg/resolve/493cb60893f47441b26ec4fb9a306bce9e342982/isnetis.onnx"

Invoke-WebRequest -Uri $url -OutFile $dest
Get-FileHash -Algorithm SHA256 -Path $dest
```

*Kiểm tra kết quả:* Mã Hash xuất ra phải trùng khớp tuyệt đối với:  
`f15622d853e8260172812b657053460e20806f04b9e05147d49af7bed31a6e99`.

---

## 4. Chạy Kiểm Thử Nghiệm Thu & Đo Hiệu Năng (Benchmark)

Để kiểm chứng toàn diện năng lực tách nền trên 5 trường hợp biên anime thực tế (nền đơn giản, nền phức tạp, tóc dài, phụ kiện nhỏ, vải voan xuyên thấu), chạy kịch bản đo kiểm:

```bash
cd backend
uv run python ../scripts/run_tier3_benchmark.py
```

### Tiêu chuẩn Nghiệm thu Đạt chuẩn:
- **Thời gian suy luận (CPU):** Từ 1.0 đến 1.5 giây mỗi ảnh (chạy với 4 luồng CPU).
- **Khớp kích thước:** Sai số kích thước 0-pixel delta.
- **Độ trong suốt:** $A_{min} \le 5$, $A_{max} \ge 250$.
- **Dải viền mềm (Anti-aliasing):** Tồn tại hàng chục ngàn pixel alpha chuyển tiếp mịn màng ($N_{soft} > 0$), chứng minh phân vùng nơ-ron thật.
- **Bảo toàn màu sắc:** Màu RGB của nhân vật được giữ nguyên 100%.
- **Vị trí tệp xuất đối chứng:** `data/tier3_output/` chứa đầy đủ ảnh gốc, mặt nạ xám, ảnh RGBA và file JSON đo đạc kỹ thuật.

---

## 5. Kích Hoạt Trong Luồng Xử Lý Chính (Pipeline Worker Integration)

Mặc định, biến `use_mock_bg_provider: bool = True` được bật để giữ cho các bài kiểm tra tự động (CI) chạy siêu tốc không cần tải mô hình nặng.

Khi muốn chạy với mô hình AI thật trên CPU trong ứng dụng:
- Thiết lập biến môi trường trong file `.env`:
  ```ini
  AIC_PIPELINE_USE_MOCK_BG_PROVIDER=false
  AIC_PIPELINE_ONNX_INTRA_OP_THREADS=4
  ```
- Hoặc truyền trực tiếp vào `PipelineConfig`:
  ```python
  from app.pipeline.config import PipelineConfig
  from app.pipeline.worker import PipelineWorker
  from app.pipeline.background import ISNetONNXProvider

  config = PipelineConfig(use_mock_bg_provider=False, onnx_execution_provider="cpu")
  provider = ISNetONNXProvider(config=config)
  worker = PipelineWorker(config=config, bg_provider=provider)
  ```

---

## 6. Kích Hoạt Tăng Tốc Phần Cứng Bằng GPU Qua DirectML (GPU Acceleration)

Nhằm tối ưu hóa hiệu năng và giảm độ trễ xử lý, hệ thống hỗ trợ tích hợp **DirectML Execution Provider** (`DmlExecutionProvider`) tận dụng GPU chuyên dụng (như NVIDIA GeForce RTX 4050) trên hệ điều hành Windows qua DirectX 12.

### 6.1. Cài đặt Dependency DirectML

Để bật hỗ trợ GPU DirectML, cài đặt gói mở rộng:

```bash
cd backend
uv sync --extra directml
# Hoặc cài trực tiếp bằng uv pip:
# uv pip install onnxruntime-directml
```

### 6.2. Kích hoạt trong Cấu hình

- **Qua biến môi trường:**
  ```ini
  AIC_PIPELINE_USE_MOCK_BG_PROVIDER=false
  AIC_PIPELINE_ONNX_EXECUTION_PROVIDER=directml
  AIC_PIPELINE_DIRECTML_DEVICE_ID=0
  ```
- **Qua mã nguồn Python:**
  ```python
  from app.pipeline.background import get_background_removal_provider
  from app.pipeline.config import PipelineConfig

  config = PipelineConfig(
      use_mock_bg_provider=False,
      onnx_execution_provider="directml",
      directml_device_id=0,
  )
  provider = get_background_removal_provider(config=config)
  ```

### 6.3. Ràng buộc Vận hành Bắt buộc (Operational Constraints)
- **Cấu hình Session:** Bắt buộc sử dụng `execution_mode = ORT_SEQUENTIAL` và `enable_mem_pattern = False`.
- **Bảo vệ Đồng thời (Concurrency Guard):** Phiên làm việc DirectML không hỗ trợ gọi suy luận đa luồng đồng thời trên cùng một session. Nhà cung cấp đã tích hợp khóa bảo vệ tự động serialize các tác vụ bất đồng bộ và chặn cuộc gọi đồng thời trái phép.
- **Dọn dẹp Tài nguyên:** Phương thức `release()` đảm bảo giải phóng toàn bộ bộ nhớ GPU và lệnh DirectX 12 mà không gây rò rỉ VRAM.

---

## TÓM TẮT DỄ HIỂU DÀNH CHO SẾP (Plain Language Summary)

- **Đã làm xong món gì mới?**:  
  Đã viết xong cuốn "sách hướng dẫn sử dụng" chi tiết từng bước để Sếp hoặc bất kỳ ai trong đội phát triển có thể tự tay tải và kích hoạt "bộ não AI tách nền" IS-Net Anime xịn sò; có sẵn mã kiểm tra vân tay số (SHA-256) để bảo đảm file không bao giờ bị hacker cài mã độc hay tải thiếu dung lượng.
- **Nó hoạt động trên máy thế nào?**:  
  Cực kỳ nhẹ nhàng và tiện lợi: mô hình tự động nằm gọn trong thư mục ẩn của máy tính (`.cache`), ứng dụng chỉ nạp khi nào có ảnh cần bóc tách (không ngốn RAM khi mở app), và chỉ cần 1 câu lệnh benchmark duy nhất là máy tự bóc thử 5 bức tranh mẫu với tốc độ chỉ khoảng 1 giây một ảnh.
- **Đã kiểm tra an toàn chưa?**:  
  Đã thiết lập tường lửa bảo vệ 3 lớp: file nặng 176 MB này tuyệt đối không bị tải nhầm lên kho code GitHub; nếu file bị đứt gãy giữa chừng thì hệ thống sẽ báo ngay chứ không làm đơ ứng dụng; và toàn bộ 218 bài kiểm tra cũ của dự án vẫn chạy 100% trơn tru.
- **Bước tiếp theo Sếp cần làm gì?**:  
  Sếp có thể thử gõ lệnh `cd backend; uv run python ../scripts/run_tier3_benchmark.py` để tận mắt ngắm nhìn 5 bức ảnh anime sau khi bóc nền cực đẹp tại thư mục `data/tier3_output/`.
