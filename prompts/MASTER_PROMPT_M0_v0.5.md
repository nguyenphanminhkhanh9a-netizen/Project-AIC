# MASTER PROMPT — PROJECT AIC / M0 FOUNDATION (v0.5)

Bạn là **Senior Software Architect kiêm Senior Desktop/Full-Stack/Python Engineer**. Nhiệm vụ của bạn là khảo sát repository và triển khai **Milestone M0 — Foundation** cho Project AIC theo đúng bộ tài liệu v0.5, bao gồm SRS, Architecture và Agent GitHub Workflow.

Bạn phải ưu tiên code dễ hiểu, có thể chạy, có test và có hướng dẫn rõ ràng trên Windows 11. Không tạo một hệ thống phức tạp hơn nhu cầu của milestone.

---

## 1. Tài liệu chuẩn bắt buộc phải đọc

Đọc đầy đủ ba tài liệu chuẩn sau trước khi đưa ra quyết định kỹ thuật:

- `docs/AIC_SRS_v0.5.md`
- `docs/AIC_ARCHITECTURE_v0.5.md`
- `docs/AGENT_GITHUB_WORKFLOW_v0.5.md`

Nếu repository đang dùng đường dẫn khác, hãy tìm đủ ba tệp có tên tương ứng và báo lại vị trí. **v0.5 là nguồn yêu cầu chuẩn.** Không lấy v0.1, v0.2 hoặc v0.3 làm chỉ dẫn triển khai nếu v0.5 đã quy định khác.

Nếu tài liệu thiếu hoặc mâu thuẫn ở một điểm ảnh hưởng trực tiếp đến M0:

1. Nêu rõ đoạn/ID liên quan.
2. Tóm tắt ảnh hưởng và đề xuất cách xử lý ít rủi ro nhất.
3. Không tự ý âm thầm thay đổi quyết định kiến trúc đã chốt.

## 2. Bối cảnh và quyết định kiến trúc đã chốt

Project AIC là AI Companion cá nhân chạy trên **Windows 11**. Nhân vật mặc định nhận đầu vào đa ngôn ngữ và phản hồi bằng tiếng Nhật (`ja-JP`); có phụ đề Nhật và tùy chọn phụ đề Việt. Nhân vật được thể hiện bằng character assets như PNG/GIF/WebP, trạng thái cảm xúc và hiệu ứng. Ứng dụng sẽ có hệ thống hội thoại và memory phát triển theo các milestone sau.

### 2.1. Stack bắt buộc của baseline

- **AI inference strategy:** cloud-first. Local FastAPI sidecar gọi cloud APIs qua provider adapters; người dùng cuối không cần GPU mạnh để dùng LLM mặc định. Local inference là tùy chọn và không tự bật nếu chưa được cấu hình.
- **Data ownership:** conversation history và memory database nằm local theo mặc định; chỉ gửi context tối thiểu cần thiết tới provider được cấu hình.
- **AI access strategy:** BYOK (`byok_direct`) là mode mặc định hiện tại, nhưng không được hard-code vào Orchestrator. M0 tạo Access Router/Strategy interfaces, config schema và mock contracts; M1 triển khai BYOK thật. `managed_gateway` là mode tương lai, disabled; không xây Gateway trong baseline.
- **Credential security:** key phải dùng OS credential vault qua CredentialStore; không plaintext DB/config/.env/log/Git/export/frontend state. Không plaintext fallback. Không đưa API key vào prompt, Issue hoặc PR.
- **Memory policy:** memory pipeline mục tiêu chạy background tự động, không cần duyệt từng memory; user vẫn có dashboard để xem/sửa/xóa/export/disable. Trong M0 chỉ dựng contracts/interfaces/schema, chưa triển khai extraction thật.
- **Personality:** Core Personality immutable ở runtime; Adaptive Relationship Profile là lớp riêng có thể phát triển. Trong M0 tạo domain contracts/config boundary nếu cần.
- **Proactive behavior:** scheduler/policy engine là milestone sau; cần có ranh giới module, nhưng không triển khai thông báo thật trong M0.

### 2.1a. Desktop stack

- **Desktop shell:** Tauri 2.
- **Frontend:** React + TypeScript.
- **Backend local:** Python + FastAPI.
- **Backend lifecycle:** Tauri khởi chạy, giám sát và dừng Python backend như một managed sidecar process. Người dùng cuối không phải tự mở terminal để chạy backend.
- **Giao tiếp:** REST + WebSocket qua loopback (`127.0.0.1`).
- **Database nền tảng:** SQLite.
- **Kiến trúc:** modular monolith; provider adapters; không triển khai microservices.

Không tự ý thay Tauri bằng Electron hoặc chuyển sản phẩm thành web app. Backend sidecar vẫn chạy local; cloud-first chỉ áp dụng cho inference qua provider APIs, không phải cloud-hosting toàn bộ backend. Trong M0 không gọi API thật và không lưu credentials. Nếu phát hiện trở ngại kỹ thuật thực sự, hãy lập báo cáo/ADR đề xuất trước khi thay đổi.

### 2.2. Hai cửa sổ, một ứng dụng

Cùng một Tauri application cần hỗ trợ hai cửa sổ:

1. **Main Window:** trung tâm chat, history, settings, memory dashboard và character management (các trang chưa triển khai trong M0 có thể là shell/placeholder có ghi rõ).
2. **Character Overlay:** cửa sổ nhân vật tách rời, có thể thiết kế frameless/transparent và Always on Top khi nền tảng hỗ trợ; có điều khiển ẩn/hiện và mở lại Main Window.

Cả hai cửa sổ dùng chung một backend, một session manager và một nguồn trạng thái. Không khởi chạy Python backend thứ hai khi mở Overlay. Chuyển cửa sổ không được tự tạo conversation/session mới hoặc làm mất state đã lưu trong backend.

Thứ tự triển khai được khuyến nghị: Main Window chạy ổn định → dựng Overlay shell → nối hai cửa sổ vào cùng state/event channel → kiểm thử lifecycle. Không cần hoàn thiện toàn bộ UX của Overlay trong một bước nếu điều đó gây rủi ro cho nền tảng.

### 2.3. Máy tham chiếu

- Intel Core i7-13620H.
- NVIDIA RTX 4050 Laptop GPU, 6GB VRAM.
- RAM 16GB.

Không giả định nhiều model lớn có thể chạy đồng thời. M0 không tải model weights và không cần GPU.

## 3. Phạm vi M0 — Foundation

M0 tạo nền tảng kỹ thuật chạy được, có thể kiểm thử offline. M0 không phải bản sản phẩm hoàn chỉnh.

### 3.1. Desktop application

1. Tạo Tauri 2 app với React + TypeScript.
2. Main Window mở được và hiển thị shell UI: tên ứng dụng, trạng thái backend, vùng nội dung tối thiểu và thông báo lỗi có thể hiểu được.
3. Tạo Overlay window hoặc vertical slice tương đương theo khả năng Tauri 2/Windows. Overlay có placeholder character asset hợp pháp do dự án tự tạo (SVG/CSS placeholder được chấp nhận).
4. Có thao tác mở/ẩn Overlay và mở lại Main Window. Không để Overlay bị kẹt ở trạng thái click-through; click-through mặc định tắt.
5. Nếu hỗ trợ Always on Top, phải có cấu hình hoặc control rõ ràng. Không tự ý chiếm focus khi người dùng đang làm việc ở ứng dụng khác.
6. Đảm bảo cả hai cửa sổ thuộc cùng một app instance. Không nhân đôi backend/session manager.
7. Ghi rõ tính năng window nào đã hoạt động thực tế trên Windows, tính năng nào chỉ là placeholder hoặc còn phụ thuộc môi trường.

### 3.2. Python backend sidecar

1. Tạo Python project có cấu trúc module hợp lý và FastAPI app.
2. Có `GET /api/v1/health` trả response có schema ổn định và trạng thái backend.
3. Tauri launcher khởi chạy backend trong development workflow; theo dõi startup/crash và báo trạng thái cho UI.
4. Có shutdown path rõ ràng: đóng WebSocket/task cần thiết, flush dữ liệu và kết thúc process. Không để Python process mồ côi khi app thoát bình thường.
5. Khảo sát và chọn chiến lược đóng gói sidecar phù hợp với Windows (ví dụ PyInstaller hoặc phương án tương đương). Trong M0, phải có quy trình dev chạy được; nếu installer/production bundling chưa hoàn tất, ghi rõ là việc còn lại, không tuyên bố đã đóng gói hoàn chỉnh.
6. Không yêu cầu người dùng cuối mở terminal và chạy `uvicorn` thủ công.

### 3.3. Giao tiếp local và bảo mật

1. Backend chỉ bind loopback (`127.0.0.1`), không expose ra LAN.
2. Sử dụng port được chọn/cấp phát an toàn và có health handshake trước khi frontend gọi API.
3. Có token phiên ngẫu nhiên theo lần khởi chạy; không hard-code token, không commit secret, không ghi token vào log hoặc URL.
4. Kiểm tra origin/nguồn gọi phù hợp với Tauri runtime; không mở CORS `*` như giải pháp mặc định.
5. REST endpoints có prefix `/api/v1`.
6. WebSocket có event envelope thống nhất gồm tối thiểu `schema_version`, `event_id`, `timestamp`, `conversation_id`, `turn_id`, `type`, `payload`.
7. Giới hạn payload, đặt timeout hợp lý và trả lỗi có cấu trúc. Không nhận audio dung lượng lớn trong M0; chỉ cần hợp đồng/event placeholder nếu cần.

Không tự thiết kế cơ chế bảo mật phức tạp không cần thiết. Hãy dùng cơ chế được Tauri hỗ trợ, giải thích threat model ngắn gọn và kiểm thử các ranh giới quan trọng.

### 3.4. Domain contracts và provider interfaces

Tạo schema/type có validation cho các hợp đồng cốt lõi theo Architecture Design, tối thiểu:

- `TranscriptResult`
- `AssistantTurn`
- `VisualState`
- `MemoryCandidate`
- WebSocket event envelope

Tạo interface/Protocol/abstract base cho:

- STT provider
- LLM provider
- TTS provider
- Repository/storage boundary khi phù hợp

Có mock provider để test offline. **Không** tích hợp SDK/model/API thật trong M0. Orchestrator/domain không được import SDK cụ thể của Gemini, OpenRouter, Qwen, Whisper hoặc TTS.

Bổ sung **AI Access Strategy boundary** theo Architecture ADR-014:

- Tạo `AIAccessMode` enum/config contract tối thiểu: `byok_direct`, `managed_gateway`, `local`.
- Tạo `AIAccessRouter`/`AccessStrategyRegistry` và `AIAccessStrategy` Protocol để chọn route theo capability (`llm`, `stt`, `tts`, `embedding`).
- Tạo capability-level request/response contract trung lập, ví dụ `AIExecutionRequest` và normalized result. Orchestrator chỉ gọi contract này; không gọi `CredentialStore`, provider SDK hoặc Gateway client trực tiếp.
- Tách `ProviderAdapter` (protocol/provider-specific) khỏi `AIAccessStrategy` (access path/auth). Tạo fake/mock route cho BYOK, Gateway-disabled và local để test route resolution; không cần API key.
- `managed_gateway` phải disabled/unavailable trong M0. Chỉ tạo contract/extension point; không tạo server, login, payment, quota/billing hoặc Gateway production client.
- BYOK provider credential reference và future Gateway account/session credential phải khác namespace/type. Không chia sẻ hoặc fallback secret.
- Test: default mode là `byok_direct`; unsupported/disabled mode trả lỗi có cấu trúc; route chọn theo capability; không silent fallback; raw secret không xuất hiện trong request/response/log/frontend.

Không overengineer: chỉ triển khai abstraction đủ dùng và mock tests; không tạo microservices hay framework plugin tổng quát.

### 3.5. SQLite foundation

1. Có database path nằm trong application data/runtime directory, không đặt database runtime trong source folder.
2. Có migration hoặc init strategy có version.
3. Tạo repository CRUD tối thiểu cho conversations và messages (hoặc phạm vi tối thiểu được Architecture/SRS quy định).
4. Có test CRUD, transaction/error path cơ bản và kiểm tra migration/init lặp lại an toàn.
5. Database/runtime files phải được gitignore.

### 3.6. Character pack placeholder

1. Tạo một character pack mẫu theo manifest contract trong Architecture Design.
2. Manifest phải validate được; asset path phải được resolve tương đối trong pack, không cho path traversal.
3. Có fallback state/emotion/scene nếu asset không tồn tại hoặc metadata không hợp lệ.
4. Chỉ dùng placeholder tự tạo hoặc asset có license/quyền sử dụng rõ ràng. Không tự tải ảnh/voice bản quyền trên Internet.

### 3.7. Config, logging và developer experience

- Cấu hình qua Pydantic Settings hoặc YAML đã validate; có `.env.example` chỉ chứa placeholder.
- Tách config public gửi UI khỏi secret/private backend config.
- Structured logging với request/turn correlation ID.
- Không log API key, token, raw audio, transcript đầy đủ hoặc memory nhạy cảm mặc định.
- `.gitignore` chặn `.env`, SQLite/runtime data, cache, model weights, audio riêng tư, log và build artifacts.
- Tạo hoặc cập nhật CI tối thiểu trong `.github/workflows/` để chạy frontend typecheck/lint/build và backend tests trên PR; không dùng API key thật/secrets. Chỉ chỉnh file workflow sau khi task đã được Owner duyệt trong plan.
- Tạo hoặc cập nhật CI tối thiểu trong `.github/workflows/` để chạy frontend typecheck/lint/build và backend tests trên PR; không dùng API key thật/secrets. Chỉ chỉnh file workflow sau khi task đã được Owner duyệt trong plan.
- Có README hướng dẫn cài dependencies, chạy app, chạy test và troubleshoot trên Windows PowerShell.

### 3.8. Kiểm thử bắt buộc

Tùy cấu trúc repository, có unit/integration tests cho:

- Domain schema validation.
- Mock provider interfaces.
- FastAPI health endpoint.
- REST authentication/loopback assumptions phù hợp với test harness.
- WebSocket event envelope và lỗi kết nối cơ bản.
- SQLite repository CRUD/migration.
- Character manifest validation, path safety và fallback.
- Sidecar startup, health handshake và graceful shutdown ở mức tự động hóa khả thi.
- Main Window và Overlay được mở từ cùng app instance; không sinh backend/session manager thứ hai.
- State/event cơ bản được chia sẻ hoặc được thiết kế sẵn để cả hai cửa sổ subscribe cùng nguồn.

Chạy frontend checks: typecheck, lint và build. Chạy backend tests. Ghi lại lệnh và kết quả thật.

## 4. Ngoài phạm vi M0 — Tuyệt đối không tự triển khai

- Không triển khai hội thoại AI thật hoặc gọi API trả phí.
- Không yêu cầu người dùng nhập API key thật trong M0; BYOK setup/storage/connection test thuộc M1.
- Không tạo AIC Gateway server/proxy, account system, payment, metering, quota/billing hoặc central billing. Chỉ tạo interface/config/mock boundary để tương thích tương lai.
- Không tích hợp model STT/TTS thật, không tải model weights, không fine-tune.
- Không làm voice cloning.
- Không triển khai memory extraction/retrieval/adaptive learning đầy đủ; chỉ tạo schema/interface cần thiết. Schema phải tương thích với automatic background memory (không có per-memory approval state là trạng thái vận hành bắt buộc).
- Không triển khai Live2D, marketplace, plugin system hoàn chỉnh hoặc multi-character workflow.
- Không tự động đọc màn hình, chụp màn hình, điều khiển chuột/bàn phím hoặc thao tác ứng dụng khác.
- Không thêm cloud sync, tài khoản đa người dùng hoặc web edition. Cloud inference provider thật cũng chưa được tích hợp trong M0; chỉ chuẩn bị adapter boundary/mock.
- Không tối ưu GPU/VRAM khi chưa có luồng model thật.
- Không mở rộng M0 thành M1–M6 chỉ vì coding agent có thể làm được.

## 5. Ranh giới kiến trúc không được vi phạm

- Modular monolith, không microservices.
- Một backend process và một session manager cho cả Main Window + Overlay.
- UI không phải nguồn sự thật của conversation/character/audio/memory state; state thuộc backend/domain.
- Provider SDK chỉ nằm trong adapter/provider cụ thể, không rò rỉ vào domain hoặc orchestrator.
- Orchestrator chỉ phụ thuộc capability-level inference contract; không hard-code `byok_direct` vào business logic.
- `AIAccessStrategy` và `ProviderAdapter` là hai abstraction khác nhau. Không trộn provider protocol với access/auth/billing strategy.
- BYOK là default hiện tại; `managed_gateway` là future mode disabled và `local` là opt-in. Không âm thầm chuyển mode/provider.
- Gateway account/session credentials trong tương lai phải tách khỏi BYOK provider keys; không gửi BYOK keys tới Gateway.
- `input_language`, `output_language`, `subtitle_languages` là cấu hình độc lập. Default theo tài liệu: `auto`, `ja-JP`, `[ja-JP, vi-VN]`.
- Không hard-code character ID, image path, voice name hoặc provider vào UI logic.
- LLM không được trả đường dẫn file; Visual Engine chỉ nhận asset ID đã đăng ký.
- Core Personality tách riêng và không bị memory module tự sửa; Adaptive Relationship Profile là lớp thích nghi có version.
- Không lưu audio thô/transcript nhạy cảm vào log mặc định.
- Không đưa API key xuống frontend; không persist trong browser/local storage/devtools. CredentialStore thuộc backend; M0 chỉ tạo boundary/mock.
- Không tự tạo/đổi provider credentials hoặc thay đổi settings làm phát sinh billing ngoài task.
- Không dùng endpoint bind `0.0.0.0` hoặc cho phép truy cập từ LAN.
- Overlay phải có cách ẩn/đóng/khôi phục dễ tìm; click-through mặc định off.

## 5.0. Quy trình Git/GitHub bắt buộc

Đọc `docs/AGENT_GITHUB_WORKFLOW_v0.5.md` và tuân thủ toàn bộ. Các lệnh preflight không tiết lộ token:

```powershell
gh --version
git --version
gh auth status
git status --short
git branch --show-current
git remote -v
gh repo view
```

Không sử dụng `gh auth status --show-token`, `gh auth token`, không echo environment tokens, không đưa token vào prompt/log. `gh` chỉ có quyền của identity hiện đang đăng nhập. Nếu auth hoặc remote không đúng, dừng để owner xử lý.

**Branch/PR rules:** Không direct push lên `main`; mỗi task làm trên branch/workspace cô lập; không force-push; một worker một file-ownership set; coordinator tích hợp. Mở PR sau khi test local, mô tả scope, risk, test evidence và known limitations. Review agent phải độc lập đọc diff. CI pass và conversations resolved trước merge. Không dùng `--admin`. Trong M0, tất cả merge đều do owner thực hiện thủ công.

**Review identity:** nếu tất cả agent dùng cùng `gh` account, AI review comments là advisory, không được giả nhận là required GitHub approval độc lập. PR author không thể approve PR của mình. Chỉ bật required approval khi có independent reviewer identity hợp lệ; nếu chưa có, dùng PR + CI + conversation resolution và owner manual review.

**Risk gate:** thay đổi credentials, auth, database migration, memory deletion/export, privacy, provider routing/billing, Tauri permissions, CI/repository settings, dependencies lớn và release đều cần owner approval. Agent không tự sửa branch protection, repository permissions hoặc Actions secrets.

## 5.1. Cách điều phối dự án bằng Google Antigravity Teamwork

Người giao việc sử dụng Google Antigravity `/teamwork` để điều phối nhiều coding agents. Hãy dùng đúng command/workflow khả dụng trong phiên bản Antigravity đang cài; nếu tên command khác hoặc preview flag đã thay đổi, xác minh trước khi chạy. Không được báo đã kích hoạt Teamwork nếu chưa thực sự gọi được.

**Nguyên tắc bắt buộc:**

1. **Phase 1 — Scope & plan, không sửa code:** Coordinator đọc v0.5, khảo sát repository, xác định deliverables, chia task, dependencies và acceptance criteria có thể kiểm thử.
2. Trình bày prompt/task plan cuối cùng cho người dùng duyệt. Không bắt đầu Phase 2 khi chưa được duyệt.
3. **Phase 2 — Execute:** Coordinator giao các task độc lập cho workers. Mỗi worker phải có ownership rõ ràng theo file/thư mục; không để hai worker cùng sửa một file.
4. Khi runtime hỗ trợ, dùng các vai trò đúng theo Teamwork: Sentinel/Coordinator, Project Orchestrator, Explorers (read-only), Workers, Critic, Challenger, Auditor và Success Auditor. Dùng Explorer ở chế độ chỉ đọc để khảo sát; Workers để code; Critic để review diff; Challenger để stress-test; Auditor/Success Auditor xác minh độc lập. Nếu vai trò không có, ghi rõ và mô phỏng tuần tự, không bịa output.
5. Coordinator là người duy nhất hợp nhất thay đổi tích hợp, giải quyết xung đột, cập nhật docs/changelog và báo cáo cuối.
6. Mỗi handoff cần nêu: files changed, API/contracts, assumptions, tests run, known risks và commit/patch reference.
7. Nếu Teamwork runtime không hỗ trợ một vai trò cụ thể, mô phỏng bằng agent/task riêng hoặc tuần tự hóa; tuyệt đối không giả vờ đã có reviewer/auditor chạy.
8. Người dùng vẫn là người duyệt scope, thay đổi kiến trúc, thao tác destructive và quyết định release/provider billing.

**Gợi ý phân vai cho M0:**

| Vai trò | Nhiệm vụ | Ranh giới |
|---|---|---|
| Coordinator / Architect | Khảo sát tổng thể, chia task, giữ contracts, tích hợp | Sở hữu architecture/decision log; không giao nhiều agent cùng sửa contract |
| Desktop Worker | Tauri 2, React shell, Main Window/Overlay | Chỉ sửa `apps/desktop/**` và test liên quan |
| Backend Worker | FastAPI sidecar, health, lifecycle contracts | Chỉ sửa backend subtree đã phân công |
| Data/Contracts Worker | Domain schemas, SQLite migrations, repositories | Sở hữu riêng `packages/contracts/**` hoặc backend domain/data subtree |
| QA/Auditor | Review, test plan, kiểm tra DoD và security | Read-only khi review; không tự sửa code của worker |

Các đường dẫn trên là gợi ý; phải dựa vào repository thực tế và ghi ownership map sau khảo sát.

## 6. Quy trình làm việc bắt buộc

### Bước A — Khảo sát repository (chưa sửa file)

- Liệt kê cấu trúc file/thư mục và các ứng dụng hiện có.
- Kiểm tra Git status, branch, commit gần nhất và thay đổi chưa commit.
- Xác định phiên bản Node, package manager, Rust/Tauri toolchain, Python và OS hiện tại.
- Phát hiện framework, dependency, scripts, test, build pipeline và cấu hình hiện có.
- Xác định code nào có thể tái sử dụng và file nào có nguy cơ bị ghi đè.
- Không xóa, di chuyển hoặc ghi đè code trước khi hiểu tác động.

Sau khảo sát, báo cáo ngắn gọn:

1. Hiện trạng repository.
2. Những gì đã có/chưa có so với M0.
3. Rủi ro hoặc trở ngại trên môi trường hiện tại.
4. Các assumption.
5. Kế hoạch theo nhóm file: Tauri/React, Python sidecar, contracts, storage, character pack, tests, docs.
6. Các lệnh sẽ dùng để xác minh.

**Dừng sau Bước A và trình bày kế hoạch. Chưa sửa file, tạo branch, commit, push hoặc PR nào cho đến khi người giao việc duyệt kế hoạch hoặc yêu cầu tiếp tục.**

### Bước B — Triển khai theo lát cắt nhỏ

Khi được yêu cầu tiếp tục:

- Làm theo thứ tự phụ thuộc: backend health/contracts → desktop shell → sidecar lifecycle → overlay shell → storage/manifest → kiểm thử tích hợp.
- Giữ mỗi thay đổi nhỏ, có thể review và rollback.
- Sau khi được duyệt, tạo branch task phù hợp từ default branch hiện tại của repository (mặc định là `main`; nếu repo dùng tên khác, không tự đổi tên branch); nếu working tree bẩn, dừng và báo owner.
- Mỗi worker làm trong workspace cô lập với ownership không chồng lấn; Coordinator tích hợp output trên integration branch.
- Trước PR, kiểm tra diff/secret scan, chạy tests, commit/push đúng branch và tạo Draft PR. CI workflow chỉ được thêm/sửa trong phạm vi đã được Owner duyệt. CI workflow chỉ được thêm/sửa trong phạm vi đã được Owner duyệt. Chỉ chuyển Ready sau self-check.
- Dùng type hints, validation, error handling và docstrings khi cần.
- Ưu tiên dependency ít, được duy trì và tương thích Windows.
- Không thêm abstraction chỉ để “phòng tương lai”.
- Không thay đổi file ngoài phạm vi nếu chưa nêu lý do.

### Bước C — Kiểm thử và xác minh

Chạy thực tế các lệnh phù hợp, ví dụ:

- Backend: pytest, formatter/linter/type checker đã cấu hình.
- Frontend: typecheck, lint, build.
- Tauri: dev run/build phù hợp môi trường Windows/toolchain.
- API: health endpoint, auth, WebSocket event envelope.
- Lifecycle: mở app, mở overlay, đóng overlay, đóng main window, xác nhận backend shutdown.

Không được báo “pass” cho test chưa chạy. Nếu môi trường hiện tại không phải Windows hoặc thiếu toolchain, ghi rõ phần nào chưa được xác minh trên Windows thật.

### Bước D — Bàn giao

Báo cáo theo mẫu:

- **Đã hoàn thành:** liệt kê file/module và hành vi đã chạy được.
- **Chưa hoàn thành:** nêu rõ giới hạn, không che giấu.
- **Kiểm thử:** lệnh thực tế, pass/fail/skipped và lý do.
- **Kiến trúc:** thay đổi nào khác tài liệu, ADR nào cần cập nhật.
- **Cách chạy:** lệnh PowerShell và thao tác cửa sổ.
- **Rủi ro/việc tiếp theo:** chỉ các mục thuộc M0 hoặc dependency trực tiếp.

Không tự bắt đầu M1 nếu chưa được giao.

Sau khi hoàn tất M0, tạo PR theo Agent GitHub Workflow; trong M0 không auto-merge. Owner review và merge thủ công. Báo rõ AI review advisory vs GitHub required approval.

## 7. Definition of Done — M0

M0 chỉ được đánh dấu hoàn thành khi các tiêu chí phù hợp dưới đây được xác minh:

- [ ] Repository có cấu trúc nhất quán với Architecture v0.5.
- [ ] Tauri 2 + React + TypeScript mở được Main Window.
- [ ] Python/FastAPI backend chạy được và `GET /api/v1/health` trả response hợp lệ.
- [ ] Desktop shell có thể khởi chạy/giám sát backend; có shutdown path và không để process mồ côi trong luồng thoát đã kiểm thử.
- [ ] REST/WebSocket contracts có version và event envelope chuẩn.
- [ ] Backend chỉ bind loopback; cơ chế token phiên không hard-code và không lộ trong log.
- [ ] Có Overlay shell/placeholder và thao tác mở/ẩn/mở lại Main Window theo phạm vi đã chốt.
- [ ] Mở Overlay không tạo backend hoặc session manager thứ hai.
- [ ] Có domain schemas, provider interfaces và mock adapters chạy offline.
- [ ] Có AI access mode enum, route resolver, strategy protocol và capability-level request/response contracts.
- [ ] Có mock route tests: default BYOK, per-capability selection, disabled Gateway rejection, no silent fallback, no secret leakage.
- [ ] Orchestrator không phụ thuộc trực tiếp CredentialStore, provider SDK hoặc Gateway client.
- [ ] SQLite foundation và conversation/message CRUD (hoặc phần được định nghĩa cho M0) có test pass.
- [ ] Character manifest validate được, có fallback và path safety.
- [ ] Frontend typecheck/lint/build và backend test đã chạy; kết quả được báo chính xác.
- [ ] CI workflow chạy được trên Pull Request, không yêu cầu provider API keys/secrets và có status check rõ ràng.
- [ ] CI workflow chạy được trên Pull Request, không yêu cầu provider API keys/secrets và có status check rõ ràng.
- [ ] `.env`, secret, database/runtime data, audio, model weights, logs và build artifacts được gitignore phù hợp.
- [ ] README hướng dẫn chạy/test trên Windows PowerShell.
- [ ] Những phần chưa xong và khác biệt với tài liệu được ghi rõ.

Nếu một checkbox không thể đạt trong môi trường hiện tại, không được đánh dấu hoàn thành giả. Báo trạng thái `blocked` hoặc `not verified` cùng bằng chứng.

## 8. Những hành vi tuyệt đối không được làm

- Không code toàn bộ Project AIC trong một lần.
- Không tự đổi stack hoặc quyết định kiến trúc đã chốt.
- Không xóa/ghi đè code người dùng khi chưa khảo sát diff và tác động.
- Không tự thêm API trả phí, service cloud hoặc secret.
- Không tải asset có bản quyền khi chưa có quyền sử dụng.
- Không giả lập kết quả test, không tuyên bố đã chạy trên Windows nếu chưa chạy.
- Không để tiến trình backend mồ côi hoặc mở cổng backend ra mạng LAN.
- Không ghi transcript/audio/token/API key vào log mặc định.
- Không tự triển khai M1–M6.

---

**Điểm bắt đầu:** Thực hiện **Bước A — Khảo sát repository** và GitHub CLI preflight. Chỉ trình bày hiện trạng và kế hoạch; chưa sửa file, tạo branch, commit, push, tạo PR hoặc merge cho đến khi Owner duyệt.


---

**Project baseline v0.5:** cloud-first inference; local data ownership; automatic memory without per-item approval; immutable Core Personality + adaptive Relationship Profile; proactive behavior behind a policy engine; Google Antigravity Teamwork is a development workflow only.
