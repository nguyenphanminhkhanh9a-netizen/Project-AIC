# Project AIC — Design Pack v0.5

**Baseline:** Windows Desktop · Tauri 2 · React + TypeScript · Python/FastAPI local sidecar · Main Window + Character Overlay  
**AI runtime:** Cloud-first · BYOK (`byok_direct`) mặc định · AI Access Strategy extensible · Local inference tùy chọn  
**Development:** Google Antigravity `/teamwork` + Git/GitHub Branch/PR/CI workflow  
**Phiên bản:** 0.5  
**Ngày cập nhật:** 04/11/2026

## 1. Danh mục 6 thành phần

| # | Tệp | Vai trò |
|---:|---|---|
| 1 | `README.md` | Hướng dẫn đọc, sử dụng và quản lý version. |
| 2 | `docs/AIC_SRS_v0.5.md` | Yêu cầu sản phẩm, BYOK mặc định, Gateway-ready access strategy, memory và proactive companion. |
| 3 | `docs/AIC_ARCHITECTURE_v0.5.md` | Kiến trúc desktop, AI Access Router, provider adapters, credential boundaries, memory/privacy và ADR. |
| 4 | `docs/AGENT_GITHUB_WORKFLOW_v0.5.md` | Quy trình Teamwork + Git/GitHub, branch, PR, CI, review, merge safeguards và thay đổi AI access mode. |
| 5 | `prompts/MASTER_PROMPT_M0_v0.5.md` | Prompt điều phối agent khảo sát và triển khai M0. |
| 6 | `Project_AIC_Design_v0.5.docx` | Word tổng hợp SRS, Architecture và GitHub Workflow. |

## 2. Quyết định đã chốt trong v0.5

- **Desktop:** Windows 11, Tauri 2 + React/TypeScript; Python/FastAPI local sidecar.
- **Display:** Main Window + Character Overlay; cùng một backend/session/state.
- **AI inference:** Cloud-first. Người dùng cuối không cần GPU mạnh; local provider là tùy chọn.
- **AI access default:** BYOK (`byok_direct`). Người dùng tự nhập API key và thanh toán trực tiếp cho provider.
- **Extensibility:** AI Access Router/Strategy Registry tách access path khỏi model/provider protocol. Kiến trúc định danh `byok_direct`, `managed_gateway` (future, disabled) và `local` modes. Có thể định tuyến theo capability mà không sửa Conversation Orchestrator.
- **Gateway status:** Chưa triển khai. Chỉ xem xét khi Owner có quyết định sản phẩm/kinh doanh, ADR, threat model, account/auth, billing/usage, quota, abuse, privacy/retention và vận hành server. BYOK có thể tiếp tục chạy song song.
- **Credential separation:** BYOK provider keys dùng OS credential vault. Future Gateway account/session token là credential type riêng, không nhận hoặc lưu BYOK keys.
- **Cost/data routing:** Không âm thầm đổi provider, model hoặc access mode. Hiển thị provider/model, mode, nơi dữ liệu được gửi và bên chịu billing.
- **Memory:** Tự động xử lý nền; user xem/sửa/xóa/export/tắt-bật được. Credentials và dữ liệu nhạy cảm bị loại.
- **Personality:** Core Personality giữ nguyên; Adaptive Relationship Profile phát triển theo tương tác.
- **Proactive:** Có policy controls, quiet hours, cooldown, daily cap, snooze.
- **Development:** Antigravity Teamwork điều phối agent; Git/GitHub quản lý branch/PR/CI. Agent không làm trực tiếp trên default branch.

## 3. Đọc và sử dụng

1. `docs/AIC_SRS_v0.5.md` — sản phẩm cần làm gì và tiêu chí nghiệm thu.
2. `docs/AIC_ARCHITECTURE_v0.5.md` — module, data flow, AI Access Strategy, credential/privacy boundaries và ADR.
3. `docs/AGENT_GITHUB_WORKFLOW_v0.5.md` — phân vai, workspace isolation, GitHub CLI, PR, CI và merge policy.
4. `prompts/MASTER_PROMPT_M0_v0.5.md` — prompt giao Antigravity Teamwork khảo sát và lập kế hoạch M0.
5. `Project_AIC_Design_v0.5.docx` — bản tổng hợp để đọc/lưu trữ.

## 4. BYOK hiện tại và Gateway tương lai

BYOK là cách dùng chính thức trong baseline hiện tại. Người dùng đăng ký trực tiếp với provider, tự tạo key, nhập vào Settings và trả chi phí trực tiếp cho provider. Local backend gọi provider qua HTTPS; key lưu trong OS credential vault.

AIC không hard-code giả định BYOK vào Orchestrator. Mọi request đi qua AI Access Router và capability-level contract. Nhờ vậy, trong tương lai có thể thêm AIC Managed Gateway hoặc local inference route. Đây là **khả năng mở rộng kiến trúc**, không phải Gateway đã hoạt động hay có thể bật tức thì bằng một config flag. Gateway cần server/account/auth, server-side secrets, metering, quota/billing, abuse prevention, privacy/retention, operations và review riêng.

Không bao giờ gửi BYOK provider key tới AIC Gateway. Gateway session token (nếu có trong tương lai) là secret riêng và có lifecycle riêng.

## 5. M0 làm gì liên quan đến AI access?

- Tạo `AIAccessMode`, `AIAccessRouter`/`AccessStrategyRegistry`, `AIAccessStrategy` và capability-level request/response contract.
- Tách `ProviderAdapter` khỏi access strategy.
- Có mock/fake strategy tests cho default BYOK, disabled Gateway, local opt-in, route per capability, unsupported route và no silent fallback.
- Orchestrator không truy cập trực tiếp CredentialStore, provider SDK hoặc Gateway client.
- Không gọi AI API thật, không yêu cầu API key, không lưu credentials, không xây Gateway server/login/billing trong M0.

M1 triển khai BYOK direct route và OS credential storage. Gateway chỉ có thể là milestone tương lai riêng sau khi được Owner duyệt.

## 6. Hướng dẫn bắt đầu

1. Giải nén pack và chép SRS, Architecture, Agent Workflow vào repository của Project AIC trong `docs/`; prompt đặt trong `prompts/`. Không ghi đè thay đổi hiện có của repository.
2. Mở đúng repository trong Antigravity.
3. Kiểm tra `git status --short`, `gh --version`, `gh auth status`, `gh repo view`. Không hiển thị hoặc trích xuất token.
4. Khởi động `/teamwork` bằng `MASTER_PROMPT_M0_v0.5.md`.
5. Phase đầu chỉ khảo sát read-only, kiểm tra repo/GitHub và trình bày kế hoạch; chưa sửa code, tạo branch, push hoặc PR.
6. Kiểm tra plan và file ownership; chỉ cho triển khai sau khi Owner duyệt.

## 7. Quản lý version

- v0.5 là baseline mới nhất; v0.4 và các bản trước được giữ nguyên làm lịch sử.
- Khi thay đổi quyết định, cập nhật SRS, Architecture/ADR, Agent Workflow và prompt liên quan.
- Không tự bật Gateway, tạo billing service hoặc thay đổi access mode production khi chưa có Owner approval.

---

**Nguồn yêu cầu chuẩn:** SRS v0.5 + Architecture v0.5 + Agent GitHub Workflow v0.5.
