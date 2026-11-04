# PROJECT AIC — ARCHITECTURE DESIGN

**Mã dự án:** AIC  
**Phiên bản:** 0.5  
**Ngày:** 04/11/2026  
**Trạng thái:** Kiến trúc baseline; BYOK là access mode mặc định trên nền tảng access-strategy extensible; Autonomous Multi-Agent GitHub Workflow đã được chốt

---

## 1. Mục tiêu kiến trúc

Kiến trúc phải đáp ứng năm yêu cầu: (1) tạo một vertical slice chạy được sớm; (2) thay thế STT/LLM/TTS mà không sửa domain logic; (3) mở rộng từ text sang voice, visual và memory theo milestone; (4) vận hành được trên Windows 11; cloud-first inference giúp không phụ thuộc GPU mạnh, còn local providers được kiểm soát tài nguyên; đồng thời hỗ trợ cửa sổ chính và overlay nổi trong cùng một ứng dụng desktop. Inference mặc định cloud-first để giảm phụ thuộc phần cứng; memory chạy tự động trong nền; proactive behavior được kiểm soát bởi policy engine.

## 2. Quyết định kiến trúc chính

### ADR-001 — Modular monolith trước microservices

**Quyết định:** Backend là một ứng dụng Python/FastAPI, chia module theo domain. Chưa tách thành nhiều service/container trong MVP.

**Lý do:** Ít overhead, dễ debug và deploy local; vẫn có ranh giới module để tách service sau này.

**Hệ quả:** Module giao tiếp qua interface/use case/event nội bộ; không import chéo tùy tiện. Tách service chỉ khi có nhu cầu tải độc lập hoặc scale độc lập.

### ADR-002 — Provider adapter cho AI models

**Quyết định:** Tất cả model/API bên ngoài được bao bọc bằng interface nội bộ.

Các interface tối thiểu:

- `STTProvider.transcribe(audio, options) -> TranscriptResult`
- `LLMProvider.generate(messages, options) -> AsyncIterator[LLMChunk]` hoặc response chuẩn hóa
- `TTSProvider.synthesize(text, voice_profile, options) -> AudioResult/AsyncIterator[AudioChunk]`
- `EmbeddingProvider.embed(texts) -> vectors` (optional, M4)
- `MemoryStore` / `ConversationRepository` là abstraction cho persistence

**Không được:** import SDK của Gemini/Qwen/OpenRouter trực tiếp trong domain service hoặc UI.

### ADR-003 — Japanese-first output tách khỏi input language

**Quyết định:** Locale đầu vào, locale đầu ra và locale phụ đề là ba cấu hình khác nhau.

```yaml
language:
  input: auto
  output: ja-JP
  subtitles:
    - ja-JP
    - vi-VN
```

LLM nhận transcript gốc cùng metadata ngôn ngữ, sau đó sinh câu trả lời tiếng Nhật. Translation subtitle là output phụ, không được đưa vào TTS mặc định.

### ADR-004 — Character pack là dữ liệu, không phải logic

**Quyết định:** Mỗi nhân vật được mô tả bởi config/versioned files gồm persona, voice profile, assets, emotion mapping và subtitle style. Frontend/backend core không được hard-code tên nhân vật hoặc đường dẫn asset.

### ADR-005 — Automatic memory pipeline, không phải online learning weights

**Quyết định:** Memory extraction, deduplication, confidence scoring, sensitivity filtering, conflict checks, upsert, retrieval và archive chạy tự động trong background; không yêu cầu per-memory confirmation. Người dùng vẫn có quyền xem, sửa, xóa, export và tắt/bật memory. Không tự sửa trọng số model.

**Guardrails:** nguồn và confidence đi kèm mỗi memory; dữ liệu nhạy cảm/credentials bị loại; memory confidence thấp hoặc unresolved conflict không được đưa vào retrieval; mọi thay đổi có version/change log và khả năng undo. User edits có độ ưu tiên cao hơn automatic inference.

### ADR-006 — Local data ownership + cloud-first inference

**Quyết định:** SQLite, memory database và character asset library nằm local trên máy người dùng theo mặc định. AI inference mặc định gọi cloud APIs qua provider adapters để ứng dụng dùng được trên máy không có GPU mạnh. Chỉ gửi context tối thiểu cần thiết cho provider đã cấu hình; không đồng nghĩa với cloud sync hoặc cloud-hosting toàn bộ ứng dụng. STT/TTS cũng ưu tiên cloud khi phù hợp; local providers vẫn được hỗ trợ tùy chọn.

**Credential strategy:** BYOK (`byok_direct`) là quyết định mặc định hiện tại, không phải ràng buộc kiến trúc. AI Access Router/Strategy Registry cho phép bổ sung `managed_gateway` hoặc `local` route mà không thay đổi Conversation Orchestrator. Gateway không được triển khai trong baseline; xem ADR-012 và ADR-014.

### ADR-007 — Desktop-first với Tauri shell và Python sidecar

**Quyết định:** Sản phẩm là ứng dụng desktop Windows. Tauri 2 + React/TypeScript là desktop shell/UI; Python/FastAPI chạy local dưới dạng sidecar process do shell khởi chạy, theo dõi và dừng.

**Lý do:** Có UI hiện đại, đa cửa sổ và khả năng tích hợp tính năng desktop; giữ Python cho hệ sinh thái AI/STT/TTS. Không biến FastAPI thành server public hoặc yêu cầu người dùng tự chạy backend bằng terminal.

**Hệ quả triển khai:**
- Development có thể chạy frontend và backend riêng để debug; bản phân phối phải có launcher/lifecycle do Tauri quản lý.
- Backend bind `127.0.0.1` trên cổng khả dụng, không bind `0.0.0.0`.
- Desktop shell cấp token phiên ngẫu nhiên cho frontend/backend handshake; không hard-code token.
- CORS/origin allowlist chỉ chấp nhận origin của app; mọi endpoint kiểm tra quyền truy cập phù hợp.
- Khi thoát ứng dụng, shell gửi shutdown signal, chờ graceful shutdown rồi mới force terminate nếu timeout.
- Log backend được ghi vào app data/logs; không ghi secret hoặc transcript nhạy cảm mặc định.

### ADR-008 — Hai cửa sổ, một nguồn trạng thái

**Quyết định:** Hỗ trợ `main_window` và `character_overlay` trong cùng một Tauri application. Hai cửa sổ dùng chung một backend, một session manager và một event stream; không tạo backend riêng cho từng cửa sổ.

**Hành vi:**
- Main window: chat, lịch sử, settings, memory dashboard, quản lý character pack.
- Overlay window: nhân vật, subtitle ngắn, trạng thái cảm xúc và các điều khiển tối thiểu (ẩn/hiện, mở main window, chuyển tương tác).
- Chuyển cửa sổ không tạo conversation mới, không reset emotion và không khởi tạo lại STT/LLM/TTS.
- Nếu cả hai cửa sổ cùng mở, event dispatcher phát cùng event cho các subscriber. Audio playback phải có một owner duy nhất để tránh phát lặp.
- Overlay có thể cấu hình Always on Top, drag, resize và click-through. Click-through mặc định tắt để không gây khó hiểu; cần có hotkey hoặc nút thoát chế độ click-through.
- Khi đóng main window, hành vi mặc định là hỏi/ẩn xuống tray/thoát theo cấu hình rõ ràng; không để sidecar chạy mồ côi.

**Ranh giới trách nhiệm:** Tauri window manager quản lý vòng đời/cấu hình cửa sổ; React component hiển thị; backend VisualState chỉ mô tả nhân vật cần thể hiện, không điều khiển tọa độ/kích thước cửa sổ hệ điều hành.

### ADR-009 — Proactive companion qua policy engine

**Quyết định:** Không để LLM tự quyết định gửi thông báo trực tiếp. Scheduler tạo trigger; Proactive Policy Engine kiểm tra global/per-type toggles, quiet hours, timezone, cooldown, daily cap, duplicate suppression, snooze và trạng thái background. Chỉ khi policy cho phép mới gọi provider và gửi nội dung.

**Lý do:** Giữ quyền chủ động của nhân vật nhưng tránh spam, đánh thức người dùng hoặc tiêu tốn quota ngoài ý muốn.

### ADR-010 — Core Personality cố định, Relationship Profile thích nghi

**Quyết định:** Tách Core Personality (phiên bản hóa, chỉ thay đổi qua character configuration có chủ đích) khỏi Adaptive Relationship Profile (cập nhật theo tương tác, feedback và memory). Runtime memory không có quyền ghi đè Core Personality.

### ADR-011 — Antigravity Teamwork là quy trình phát triển, không phải runtime dependency

**Quyết định:** Google Antigravity `/teamwork` được dùng để điều phối coding agents trong quá trình phát triển. Teamwork không được đưa vào sản phẩm AIC, không phải dịch vụ runtime và không được yêu cầu end-user cài Antigravity.

**Quy tắc:** phase scope/requirements trước; người dùng duyệt task prompt và acceptance criteria; sau đó mới execute. Coordinator phân quyền file ownership, workers thực hiện các phần tách biệt, reviewer/auditor kiểm tra độc lập. Nếu lệnh `/teamwork` không có trong phiên bản đang cài, agent phải xác minh cú pháp khả dụng hoặc mô phỏng quy trình tương đương mà không giả vờ lệnh đã chạy.


### ADR-012 — BYOK là mô hình credential mặc định

**Trạng thái:** Accepted — 04/11/2026.

**Quyết định:** Người dùng tự tạo và cung cấp API key cho từng provider/capability cần dùng. Local Python sidecar gọi trực tiếp cloud API qua HTTPS. Không nhúng shared key vào desktop binary; không chạy AIC-owned API gateway, proxy hoặc central billing trong baseline.

**Credential lifecycle:**
- Frontend có secret input chuyên dụng; không persist key trong localStorage/sessionStorage, Redux/devtools state persistence hoặc crash telemetry. Submit qua local authenticated IPC tới sidecar.
- Backend xử lý key trong memory, xác thực khi phù hợp và lưu qua `CredentialStore` abstraction gắn với OS credential vault (Windows Credential Manager là target đầu tiên).
- Không lưu secret trong SQLite, JSON/YAML config, `.env`, environment snapshot, log, exception text, export, backup, PR/Issue, screenshot hoặc test fixture.
- Không có plaintext fallback. Nếu secure store không sẵn sàng hoặc access denied, báo lỗi và không lưu key.
- DB chỉ giữ `credential_ref`, provider/capability/model metadata và trạng thái kết nối; không giữ raw key.
- Hỗ trợ add/test/replace/delete/revoke guidance. Không bao giờ hiển thị full key lại; có thể hiển thị provider và masked suffix nếu triển khai an toàn.
- Key không được sync với cloud hoặc đưa vào backup/export mặc định.

**Data flow:** local app → local sidecar → selected provider endpoint over HTTPS. Key chỉ được dùng làm provider authentication; không gửi qua AIC-owned server. Nội dung prompt/context vẫn có thể được provider nhận và xử lý theo terms/privacy/retention của chính provider. Local memory/history không tự động được upload.

**Cost and routing guardrails:**
- Người dùng chịu trách nhiệm billing và quota trực tiếp với provider. AIC hiển thị cost/quota khi provider cung cấp usage metadata; không tự khẳng định số dư hoặc giá nếu API không cung cấp.
- Cho phép cấu hình request/token budgets, timeout và rate limit nội bộ.
- Không tự fallback sang provider/model khác, đặc biệt khi có thể phát sinh phí hoặc thay đổi tuyến xử lý dữ liệu. Fallback chỉ chạy nếu người dùng explicitly configures it.
- BYOK credentials được tách theo capability; một LLM key không mặc định dùng được cho STT/TTS.

**Lý do:** giảm chi phí vận hành và trách nhiệm lưu giữ secret tập trung cho chủ dự án; người dùng kiểm soát provider và chi phí.

**Trade-offs:** onboarding khó hơn; người dùng phải có tài khoản/provider key và tự quản lý quota, billing, terms. AIC phải cung cấp hướng dẫn dễ hiểu cho từng provider.

### ADR-013 — Autonomous Multi-Agent GitHub Workflow có kiểm soát

**Trạng thái:** Accepted — 04/11/2026.

**Quyết định:** Google Antigravity `/teamwork` điều phối công việc đa agent; Git/GitHub là nguồn lưu vết chính thức cho source changes qua branch, commit, Pull Request, review conversation và CI. Không agent nào được làm việc trực tiếp trên `main`.

**Teamwork roles:** dùng coordinator/orchestrator, Explorer (read-only), Workers (implementation), Critic (independent code review), Challenger (adversarial tests), Auditor (integrity/test evidence) và Success Auditor (end-to-end handoff) khi runtime hỗ trợ. Phân công file ownership không chồng lấn; workspace phải cô lập. Coordinator là người duy nhất tích hợp outputs và tạo PR đại diện cho milestone/task nếu cách tổ chức repo yêu cầu.

**GitHub safeguards:**
- `main` được bảo vệ: require pull request; require relevant CI status checks; require conversation resolution; block force-push/deletion; không dùng admin bypass.
- Mỗi task có branch riêng, commit nhỏ, PR có scope, risk classification, test evidence, known limitations và liên kết Issue (nếu có).
- Không chấp nhận AI review tự động như một GitHub approval hợp lệ nếu agent đang dùng cùng identity với PR author. Pull request author không thể approve chính PR đó. AI review vẫn có giá trị advisory; approval bắt buộc phải từ identity độc lập có quyền theo GitHub rules hoặc do owner review theo repository policy.
- Auto-merge chỉ xem xét cho thay đổi low-risk sau khi CI pass, conversation resolved và tất cả branch rules thỏa mãn. Thay đổi bảo mật, credential, auth, database migration, memory deletion/export, privacy, Tauri permissions, CI workflow, dependencies hoặc release cần owner approval/manual merge.
- Tuyệt đối không dùng `gh pr merge --admin`, không tắt checks/branch rules để ép merge.
- `gh` dùng quyền của tài khoản đã đăng nhập; không đồng nghĩa với “toàn quyền” nếu tài khoản/token không có quyền đó. Tokens/secrets không được in ra terminal/log hoặc chia sẻ vào prompt.

**Rollout:** giai đoạn đầu dùng human merge mặc định cho tất cả PR trong M0; sau một số PR thành công có thể cho phép auto-merge các thay đổi low-risk.

**Lý do:** cô lập thay đổi, dễ rollback, phát hiện lỗi trước merge và giữ bằng chứng review/test; tránh nhầm lẫn giữa agent comments và các trạng thái approval được GitHub công nhận.

### ADR-014 — Strategy-based AI access routing (BYOK default, Gateway-ready)

**Trạng thái:** Accepted — 04/11/2026.

**Quyết định:** Tách `AI Access Strategy` khỏi `Model Provider Adapter`. BYOK là route mặc định hiện tại (`byok_direct`), nhưng Orchestrator chỉ phụ thuộc vào capability-level inference contract. Một `AIAccessRouter`/`AccessStrategyRegistry` resolve route theo capability và cấu hình đã lưu. Các mode được định danh chuẩn: `byok_direct`, `managed_gateway` (future, disabled) và `local` (optional).

**Trách nhiệm tách biệt:**
- `ConversationOrchestrator` tạo request chuẩn hóa và gọi capability executor; không biết secret, billing owner hay endpoint truy cập cụ thể.
- `ProviderAdapter` xử lý API/model-specific protocol, payload mapping, streaming và normalize response cho provider tương ứng.
- `AIAccessStrategy` quyết định đường thực thi, auth context và cách gọi executor.
- `ByokDirectStrategy` lấy provider credential qua `CredentialStore` ở backend local, rồi gọi provider trực tiếp qua HTTPS.
- `ManagedGatewayStrategy` (future) gọi AIC Gateway qua `GatewayClient`; dùng account/session credential riêng. Upstream model credentials chỉ nằm ở server/gateway, không chuyển xuống desktop và không nhận BYOK key.
- `LocalStrategy` gọi local inference adapter đã được người dùng cài đặt/cấu hình; không tự tải model hoặc tự bật.

**M0 scope:** tạo enums/config schema, route resolver, interfaces/Protocols, capability request/response contracts và fake/mock strategies. Test route selection, unsupported mode, no-silent-fallback và tách credential namespaces. Không triển khai AIC Gateway server, account system, billing, quota service hoặc Gateway production client.

**M1 scope:** triển khai BYOK direct route, provider adapters đầu tiên và OS CredentialStore. Không buộc UI/Orchestrator phụ thuộc vào raw API key.

**Future Gateway scope:** chỉ bắt đầu sau ADR và business/security review riêng. Cần account authentication, tenant isolation, server-side secret management, upstream provider adapter, usage metering, quotas/entitlements, billing/payment, abuse/rate controls, audit, incident response, privacy/retention terms, service availability và chi phí vận hành. Có thể cần login/account UI và account-session credential store riêng.

**Trade-offs:** abstraction tăng một lớp thiết kế nhỏ ở M0; đổi lại tránh coupling toàn bộ sản phẩm vào BYOK. Đây là gateway-ready architecture, không phải cam kết rằng Gateway có thể bật chỉ bằng một config flag: Gateway tương lai vẫn cần server, tài khoản, vận hành và các review nêu trên. BYOK có thể tiếp tục tồn tại song song làm lựa chọn user-controlled.

## 3. Sơ đồ module logic

```text
┌───────────────────────────────────────────────────────────────┐
│                  DESKTOP PRESENTATION LAYER                    │
│ Tauri 2 Desktop Shell                                            │
│ ┌────────────────────┐       ┌───────────────────────────────┐  │
│ │ Main Window        │       │ Character Overlay Window      │  │
│ │ React + TypeScript │       │ React + TypeScript            │  │
│ │ Chat/Settings/Memory│      │ Character/Subtitle/Controls   │  │
│ └────────────────────┘       └───────────────────────────────┘  │
└──────────────────────────────┬────────────────────────────────┘
                               │ Local REST + WebSocket
┌──────────────────────────────▼────────────────────────────────┐
│             LOCAL PYTHON BACKEND (MANAGED SIDECAR)              │
│                       APPLICATION CORE                         │
│ Conversation Orchestrator | Session Manager | Event Dispatcher   │
│ AI Access Router | Route Policy | Capability Resolver              │
└──────┬───────────────┬───────────────┬───────────────┬──────────┘
       │               │               │               │
┌──────▼─────┐  ┌──────▼──────┐ ┌──────▼──────┐ ┌─────▼─────────┐
│ AUDIO      │  │ LLM         │ │ CHARACTER   │ │ VISUAL        │
│ STT / VAD  │  │ Prompt      │ │ Persona     │ │ Emotion       │
│ TTS        │  │ Composer    │ │ Voice refs  │ │ Asset Manager │
└──────┬─────┘  └──────┬──────┘ └─────────────┘ │ Effects       │
       │               │                         └───────────────┘
       │          ┌────▼─────────┐
       │          │ MEMORY       │
       │          │ Extract      │
       │          │ Retrieve     │
       │          │ Adapt         │
       │          └────┬─────────┘
       │               │
┌──────▼───────────────▼────────────────────────────────────────┐
│                     PROVIDER / DATA LAYER                       │
│ Access strategies | STT/LLM/TTS adapters | CredentialStore      │
│ SQLite | Optional local inference | Vector store (optional)     │
│ Config | Local assets | Credential references (no secrets)      │
└───────────────────────────────────────────────────────────────┘
```

### 3.1. AI access strategy boundary

```text
Conversation Orchestrator
        │ normalized capability request
        ▼
AIAccessRouter / AccessStrategyRegistry
        ├── byok_direct (default now)
        │      └── ProviderAdapter + CredentialStore (OS vault)
        │              └── Selected cloud provider over HTTPS
        ├── managed_gateway (future; disabled)
        │      └── GatewayClient + separate AIC account session
        │              └── AIC Gateway server → upstream provider adapters/secrets
        └── local (optional; explicit user setup)
               └── Local provider adapter/runtime
```

`ProviderAdapter` and `AIAccessStrategy` are separate extension points. Provider adapters normalize provider-specific API formats; access strategies decide how a request reaches the chosen execution environment and which authentication boundary applies. `ConversationOrchestrator`, prompt composition, memory retrieval and UI chat flow must not contain mode-specific branching beyond displaying resolved route metadata.

The active route is resolved per capability (`llm`, `stt`, `tts`, `embedding`). User-configured capability overrides are explicit. No implicit failover between BYOK, Gateway, providers or local inference is permitted. Each execution result includes non-secret metadata (`access_mode`, `provider_id`, `model_id`, `capability`, `remote/local`, `billing_owner_label`, `data_destination_label`) for UI transparency and audit; never include raw credentials.

## 4. Desktop runtime và hai cửa sổ

### 4.1. Runtime topology

```text
Windows 11
└── Project AIC.exe (Tauri 2)
    ├── Main Window (React UI)
    ├── Character Overlay Window (React UI, transparent/always-on-top)
    └── Python Backend Sidecar (FastAPI)
        ├── Orchestrator + Session Manager (single instance)
        ├── STT / LLM / TTS provider adapters
        ├── Visual + Character + Memory modules
        └── SQLite + local assets
```

Backend là tiến trình local do Tauri quản lý. Frontend không tự khởi chạy nhiều backend khi mở thêm cửa sổ. Sidecar phải có health handshake trước khi UI gửi request.

### 4.2. Main window và overlay

| Thành phần | Main window | Character overlay |
|---|---|---|
| Mục đích | Trung tâm điều khiển | Nhân vật luôn hiện trên desktop |
| Nội dung | Chat, lịch sử, settings, memory, character manager | Character sprite/animation, subtitle, trạng thái |
| Input | Text, mic, cài đặt | Nút mic/quick action tùy chọn |
| Window behavior | Kích thước chuẩn, taskbar | Nền trong suốt, frameless, optional always-on-top |
| Quyền sở hữu audio | Có thể là playback owner | Không tự phát audio song song |
| Đóng cửa sổ | Theo app close policy | Ẩn overlay, không dừng backend |

Hai cửa sổ dùng chung `conversation_id`, `character_id`, `turn_id` và state version. Nếu cùng mở, chúng subscribe vào cùng event channel. Mỗi event có sequence/version để UI bỏ qua event cũ hoặc trùng.

### 4.3. Giao tiếp frontend/backend

- REST/WebSocket chỉ bind loopback (`127.0.0.1`); cổng được chọn động hoặc cấu hình an toàn.
- Tauri sidecar launcher truyền thông tin bootstrap qua cơ chế an toàn của desktop runtime; không ghi token vào source code hoặc URL log.
- Backend xác thực token phiên; kiểm tra origin; giới hạn payload và kích thước audio.
- Frontend có trạng thái `backend_starting`, `backend_ready`, `backend_failed`, `backend_stopping`.
- Khi backend crash, shell phát hiện, hiển thị lỗi có hướng dẫn và chỉ restart theo policy có giới hạn.
- Khi app thoát, đóng WebSocket, dừng tác vụ đang chạy, flush SQLite rồi shutdown backend.

### 4.4. Quy tắc overlay an toàn

- Luôn có cách truy cập nút đóng/ẩn và mở lại main window.
- Click-through là tùy chọn, không phải mặc định.
- Khi click-through bật, phải có hotkey toàn cục hoặc thao tác khôi phục dễ tìm.
- Overlay không được tự ý chiếm focus khi người dùng đang gõ ở ứng dụng khác.
- Không dùng overlay để chụp màn hình/đọc nội dung ứng dụng khác trong MVP.

## 5. Thành phần và trách nhiệm

| Module | Trách nhiệm | Không được làm |
|---|---|---|
| `core/orchestrator` | Điều phối lượt hội thoại, ghép context, phát event | Gọi trực tiếp SDK model cụ thể |
| `core/session` | Quản lý conversation/session/turn IDs | Lưu state chỉ trong UI |
| `ai_access` | Resolve access mode theo capability; tạo route/execution context; áp dụng explicit routing policy | Đọc/hiển thị raw secrets; tự fallback sang mode/provider khác |
| `ai_access/strategies` | BYOK direct (hiện tại), Gateway (future), local (optional) qua interface chung | Nhúng billing hoặc provider-specific prompt logic vào Orchestrator |
| `providers/stt` | Audio → transcript + language metadata | Quyết định tính cách |
| `providers/llm` | Adapter cho model chat | Truy cập database tùy tiện hoặc tự đọc secret từ UI state |
| `credentials` | CredentialStore boundary; resolve credential reference từ OS vault khi gửi request | Lưu raw key vào SQLite/config/log hoặc trả key về frontend |
| `providers/tts` | Text Nhật → audio chunks | Chọn emotion asset |
| `character` | Nạp persona/voice/config nhân vật | Hard-code provider SDK |
| `memory` | Background extraction, filter, deduplicate, resolve conflicts, upsert, retrieve, archive, undo/delete | Per-memory approval hoặc tự sửa model weights |
| `proactive` | Schedule triggers; policy check; reminders/inactivity messages; throttling | Gửi trực tiếp từ LLM bỏ qua policy |
| `personality` | Compose immutable Core Personality + adaptive relationship layer | Cho memory ghi đè Core Personality |
| `visual` | Map metadata → asset/effect hợp lệ | Tin đường dẫn file do LLM trả về |
| `repositories` | Persistence và migrations | Chứa quy tắc prompt |
| `api` | REST/WebSocket boundary | Chứa business logic lớn |
| `observability` | Structured logs, metrics, tracing IDs | Ghi secret hoặc raw audio mặc định |

## 6. Luồng dữ liệu

### 5.1. Text turn — M1

```text
User text
  → API validation
  → Conversation Orchestrator
  → Load character core + recent history + approved memories
  → Prompt Composer (enforce output_language=ja-JP)
  → AI Access Router resolves configured mode for `llm`
  → Selected AccessStrategy (BYOK direct by default)
  → Provider Adapter / normalized capability executor
  → Validate structured assistant response
  → Save message
  → Emit subtitle + visual-state events
  → AI Access Router resolves configured mode for `tts`
  → Selected AccessStrategy → TTS Provider Adapter
  → Emit audio-ready/audio-chunk events
  → Turn completed
```

### 5.2. Voice turn — M2

```text
Microphone
  → Audio capture/VAD
  → AI Access Router resolves configured mode for `stt`
  → Selected AccessStrategy → STT Provider Adapter
  → TranscriptResult(text, detected_language, confidence, segments)
  → Optional transcript correction
  → Same text-turn pipeline
  → Japanese response text
  → AI Access Router resolves configured mode for `tts`
  → Selected AccessStrategy → TTS Provider Adapter
  → Audio chunks + subtitle segments + visual events
```

Không bắt buộc dịch transcript đầu vào sang tiếng Nhật. Giữ nguyên transcript gốc, language tag và có thể thêm normalized text nếu thật sự cần.

### 5.3. Automatic memory learning — M4

```text
Conversation event
  → Background memory extractor
  → Schema validation + source attribution
  → Sensitivity/secret filter
  → Confidence + importance scoring
  → Deduplication + conflict resolution
  → Automatic upsert / supersede / archive
  → Versioned memory store + change log
  → Retrieval at relevant future turn
  → Adaptive Relationship Profile
```

No per-memory approval step. Low-confidence or unresolved conflict is excluded from active retrieval rather than repeatedly prompting the user. User can inspect/edit/delete/disable the pipeline in Memory Dashboard.

### 5.4. Proactive companion — M5

```text
Schedule / inactivity / reminder trigger
  → Proactive Scheduler
  → Policy Engine (toggles, quiet hours, timezone, cooldown, daily cap, dedupe)
  → Allowed? ── no → defer/drop and record reason
       │ yes
       → Context builder (minimal memory)
       → Cloud LLM provider adapter
       → Notification / character message
       → Snooze / done / disable feedback
```

LLM cannot bypass policy or send operating-system notifications directly.

## 7. Hợp đồng dữ liệu cốt lõi

### 7.1. TranscriptResult

```json
{
  "text": "Hôm nay tôi hơi mệt.",
  "detected_language": "vi",
  "language_confidence": 0.94,
  "segments": [],
  "provider": "faster_whisper",
  "duration_ms": 2400
}
```

Confidence và segment timestamps có thể null nếu provider không cung cấp.

### 7.2. AssistantTurn

```json
{
  "turn_id": "uuid",
  "text": "そっか。今日は少し休もうね。",
  "output_language": "ja-JP",
  "subtitle_translations": {
    "vi-VN": "Ra vậy. Hôm nay nghỉ ngơi một chút nhé."
  },
  "emotion": {
    "label": "comforting",
    "intensity": 0.65
  },
  "scene": "comfort",
  "animation": "gentle_idle",
  "effects": [],
  "tts": {
    "voice_profile_id": "default_ja_voice",
    "enabled": true
  }
}
```

Backend phải validate `emotion`, `scene`, `animation`, `effects` theo enum/registry đã cấu hình. Field không hợp lệ phải được thay bằng fallback an toàn.

### 7.3. VisualState

```json
{
  "character_id": "character_01",
  "state": "speaking",
  "emotion": "comforting",
  "intensity": 0.65,
  "scene": "comfort",
  "asset_id": "comfort_01",
  "effects": [],
  "transition_ms": 250
}
```

### 7.4. Character pack manifest

```json
{
  "schema_version": "1.0",
  "character_id": "character_01",
  "display_name": "Character One",
  "default_locale": "ja-JP",
  "persona_file": "config/persona.yaml",
  "voice_profile": "voice/default.json",
  "assets": [
    {
      "asset_id": "idle_neutral_01",
      "path": "images/idle/neutral.png",
      "format": "png",
      "state": "idle",
      "emotion": "neutral",
      "scene": "default",
      "tags": ["default", "front"],
      "priority": 100
    },
    {
      "asset_id": "happy_01",
      "path": "images/emotions/happy.gif",
      "format": "gif",
      "state": "speaking",
      "emotion": "happy",
      "scene": "default",
      "tags": ["smile", "celebration"],
      "priority": 90
    }
  ],
  "fallbacks": {
    "state": "idle",
    "emotion": "neutral",
    "scene": "default"
  }
}
```

### 7.5. MemoryCandidate

```json
{
  "memory_id": "uuid",
  "type": "communication_preference",
  "content": "Người dùng thích câu trả lời ngắn gọn khi đang căng thẳng.",
  "source_message_ids": ["message-id"],
  "confidence": 0.82,
  "importance": 0.7,
  "status": "active",
  "sensitivity": "non_sensitive",
  "version": 1,
  "updated_by": "automation",
  "change_reason": "repeated_explicit_preference"
}
```

## 8. Giao thức API và event

### 8.1. REST endpoints dự kiến

- `GET /api/v1/health` — health check.
- `GET /api/v1/config` — cấu hình công khai, không bao gồm secret.
- `GET /api/v1/characters` — danh sách character packs.
- `POST /api/v1/conversations` — tạo conversation.
- `GET /api/v1/conversations/{id}/messages` — lịch sử tin nhắn.
- `POST /api/v1/conversations/{id}/messages` — gửi text turn.
- `GET /api/v1/settings` / `PATCH /api/v1/settings` — cài đặt.
- `GET /api/v1/memories` / `PATCH` / `DELETE` — thêm ở M4.

### 8.2. WebSocket

Endpoint dự kiến: `/api/v1/ws/conversations/{conversation_id}`.

Client → server:

- `user.text.submit`
- `user.audio.start`
- `user.audio.chunk`
- `user.audio.end`
- `user.turn.cancel`
- `client.ping`

Server → client:

- `session.ready`
- `stt.partial`
- `stt.final`
- `assistant.thinking`
- `assistant.text.delta`
- `assistant.response`
- `subtitle.segment`
- `visual.state`
- `tts.audio.chunk`
- `tts.audio.completed`
- `turn.completed`
- `error`

Mọi event cần có `event_id`, `conversation_id`, `turn_id`, `timestamp`, `schema_version` và payload tương ứng. Audio chunk nên truyền binary/WebSocket frame hoặc cơ chế stream phù hợp; không base64 hóa audio lớn trong JSON nếu không cần thiết.

## 9. Data architecture

### 9.1. SQLite tables ban đầu

- `characters`: character ID, display name, pack version, config path.
- `conversations`: conversation ID, character ID, timestamps, status.
- `messages`: message ID, conversation ID, role, text, locale, metadata JSON, created_at.
- `settings`: key/value/version, không lưu secret dạng plaintext nếu có secure store.
- `voice_profiles`: profile ID, character ID, provider, model, reference metadata, consent/license notes.
- `memories` (M4): typed memory, content, confidence, source, status, timestamps.
- `memory_change_log` (M4): append-only change events, source, version, reason and undo metadata.
- `memory_candidates` may be used as a transient processing queue, not a user approval inbox; low-confidence/unresolved items are not activated.
- `proactive_rules`, `reminders`, `proactive_events` (M5): schedules, per-type settings, policy decisions, snoozes and delivery history.

### 9.2. Search

- Giai đoạn đầu: SQLite FTS5 hoặc truy vấn có cấu trúc là đủ cho history/profile.
- Khi cần semantic recall: thêm embedding provider và vector store qua interface.
- Qdrant Python client hỗ trợ local mode lưu persistent path; có thể chuyển sang Qdrant server khi cần scale. Không bắt buộc triển khai Qdrant trong M0/M1.

## 10. Provider strategy và model candidates

### Chiến lược chung: cloud-first, BYOK-default, access-mode extensible

Ứng dụng mặc định gọi AI cloud APIs qua HTTPS từ local Python sidecar. End-user không cần GPU rời hoặc model weights cục bộ để có trải nghiệm mặc định. Mỗi modality dùng provider adapter độc lập. Một AI Access Router chọn access strategy tách biệt với provider adapter; có thể đổi provider hoặc cách truy cập mà không sửa domain/orchestrator.

### LLM

LLM cloud API là đường chạy mặc định. Chọn provider/model theo chất lượng multilingual, Japanese generation, latency, cost, quota, rate limits, data retention và commercial terms. Không khóa một nhà cung cấp vào domain code. Gói miễn phí chỉ là lựa chọn, không được xem là quota đảm bảo.

Local LLM là provider tùy chọn cho người dùng muốn offline/kiểm soát dữ liệu và có phần cứng phù hợp. Không tự chuyển qua local nếu người dùng chưa cấu hình.

### STT

Ưu tiên cloud STT API khi hỗ trợ tốt ngôn ngữ đầu vào, streaming, latency và privacy. `faster-whisper` là local adapter tùy chọn, không phải dependency bắt buộc của bản phát hành mặc định. Luôn giữ text fallback.

### TTS

Ưu tiên cloud TTS có chất lượng tiếng Nhật và voice licensing phù hợp. Qwen3-TTS là một ứng viên local/self-hosted để benchmark, không phải model mặc định bắt buộc trên máy người dùng. Không quảng bá voice cloning nếu chưa xử lý rights/consent và provider terms.

### Cloud failures và BYOK credential model

Timeout, bounded retry, quota/usage visibility (nếu provider cung cấp) và provider health là bắt buộc. Cloud fail phải báo lỗi rõ. Chỉ retry hoặc chuyển sang local/provider khác khi người dùng đã cấu hình tường minh; không tự chuyển sang provider có thể phát sinh phí hoặc nhận dữ liệu theo policy khác.

BYOK (`byok_direct`) là access strategy mặc định hiện tại. Tính mở rộng được bảo đảm bằng các boundary sau:
- `AIAccessMode` enum: `byok_direct`, `managed_gateway`, `local`; chỉ mode có implementation/feature flag khả dụng mới được chọn.
- `AIAccessRouter` + `AccessStrategyRegistry` resolve mode per capability; policy từ chối unsupported/disabled route rõ ràng, không âm thầm fallback.
- `CapabilityExecutor`/Protocol cung cấp request/response chuẩn hóa cho Orchestrator. `AccessStrategy` không được làm rò secret vào normalized response.
- `ProviderAdapter` chịu trách nhiệm API-specific request, streaming và response normalization; không quyết định billing strategy.
- `CredentialStore` interface cung cấp `set`, `get`, `delete`, `exists` hoặc operation tương đương; chỉ backend được phép gọi và chỉ dành cho BYOK provider keys.
- Windows target: Windows Credential Manager/OS credential vault; implementation được bọc trong adapter. Có thể khảo sát Python `keyring` hoặc Windows native API ở M1, nhưng phải xác minh backend thực tế và không chấp nhận plaintext backend.
- `provider_profiles` lưu metadata (provider, model, capability, endpoint allowlisted, credential reference, timestamps, status), không lưu secret.
- API key được nhập qua secret field, gửi qua local authenticated IPC, xử lý trong backend memory và gửi tới đúng provider host qua HTTPS. Không đặt key trong URL/query string, frontend config, analytics, crash dump, logs, database, backup/export hoặc Git.
- Provider base URL không được cho phép tùy ý tới local/private network; custom endpoint cần allowlist/explicit advanced setting và chặn SSRF/private IP.
- Hướng dẫn BYOK phải liên kết website chính thức để tạo key, nêu provider billing/quota, data retention và cách revoke/rotate; không yêu cầu người dùng dán key vào chat/Issue.
- Không gọi cloud API tự động cho tới khi người dùng chọn provider, nhập credential và xác nhận provider/data disclosure.
- `GatewayClient` và `GatewayAccountCredentialStore` là extension points tương lai riêng; tuyệt đối không tái sử dụng `CredentialStore` namespace cho provider master keys và AIC account/session tokens.
- Không cung cấp AIC-operated gateway/shared key/central billing ở baseline. ADR-014 định nghĩa ranh giới mở rộng; việc xây gateway vẫn cần server, account/auth, metering, billing, quota, abuse prevention và privacy/operations review.

### Vector store

M4 mới quyết định có cần Qdrant hay không. Có thể bắt đầu bằng SQLite/FTS5, sau đó dùng `VectorMemoryStore` adapter.

### License và voice rights

Trước khi phân phối, phải kiểm tra license riêng của code, model weights, voice assets và character assets. Voice cloning chỉ sử dụng mẫu giọng mà người dùng có quyền sử dụng hoặc có sự đồng ý phù hợp. Không coi model open-source đồng nghĩa với mọi dữ liệu đầu vào đều được cấp phép.

## 11. Bảo mật và quyền riêng tư

- `.env` chỉ dành cho local development; commit `.env.example` không có secret. BYOK provider key không đặt trong `.env` ở bản phát hành.
- Không bao giờ gửi API key xuống frontend sau khi submit; không đóng gói shared API key trong binary desktop. Chỉ local backend CredentialStore được resolve secret.
- Conversation history, memory store và character assets nằm local theo mặc định. Cloud inference chỉ nhận context tối thiểu cần thiết của turn hiện tại.
- Onboarding/Settings phải giải thích rõ provider, model, remote/local mode và loại dữ liệu có thể được gửi tới provider. Không coi việc user bật automatic memory là đồng ý gửi toàn bộ database lên cloud.
- Audio tạm thời lưu trong thư mục temp và xóa sau xử lý mặc định; log không ghi transcript đầy đủ, raw audio, token/API key hoặc memory nhạy cảm.
- Automatic memory không yêu cầu xác nhận từng mục; thay vào đó dùng filters, confidence thresholds, source attribution, conflict policy, change log, undo và thao tác user review/edit/delete/disable.
- Không lưu credentials, password, API key, payment data hoặc dữ liệu nhạy cảm/rủi ro cao vào long-term memory. Không suy đoán sensitive traits.
- Cung cấp thao tác export/delete conversation, memory và voice reference metadata. Xóa memory phải vô hiệu hóa retrieval ngay. API credentials không bao giờ nằm trong export/backup; thao tác xóa credentials xóa tham chiếu và secret khỏi OS vault.
- Có timeout, bounded retry, quota visibility (nếu có), circuit breaker và lỗi có mã. Không tự đổi provider/model có thể phát sinh phí hoặc thay đổi data routing nếu user chưa cấu hình.
- Proactive messages phải đi qua policy engine; quiet hours, per-type/global toggles, timezone, cooldown, daily cap, deduplication và snooze được kiểm tra trước khi gọi LLM/phát thông báo.
- Nếu app đã thoát hẳn, proactive delivery chỉ hoạt động khi người dùng bật rõ background/tray/autostart.

## 12. Cấu trúc thư mục đề xuất

```text
AIC/
├── apps/
│   └── desktop/                 # Tauri 2 shell + React/TypeScript
├── backend/
│   ├── app/
│   │   ├── api/v1/
│   │   ├── core/                # config, logging, errors, events
│   │   ├── orchestrator/
│   │   ├── domain/              # entities, schemas, enums
│   │   ├── ai_access/            # Access router + strategy registry
│   │   │   ├── contracts.py
│   │   │   ├── router.py
│   │   │   └── strategies/       # BYOK direct; Gateway/local extension points
│   │   ├── credentials/         # OS credential-vault boundary
│   │   ├── providers/
│   │   │   ├── stt/
│   │   │   ├── llm/
│   │   │   ├── tts/
│   │   │   └── embeddings/
│   │   ├── character/
│   │   ├── visual/
│   │   ├── memory/
│   │   ├── repositories/
│   │   └── services/
│   └── tests/
├── character_packs/
│   └── character_01/
│       ├── manifest.json
│       ├── config/
│       ├── images/
│       ├── effects/
│       └── voice/
├── data/                        # runtime data; gitignored
├── docs/                        # SRS, architecture, ADRs, API specs
├── scripts/
├── .env.example
├── .gitignore
└── README.md
```

## 13. Testing strategy

### Unit tests

- Schema validation cho AssistantTurn, VisualState, TranscriptResult, MemoryCandidate.
- Output locale enforcement.
- Prompt composer không làm lộ secret.
- Asset resolver fallback khi thiếu file/enum.
- Automatic memory extraction filters, confidence thresholds, deduplication/conflict rules, version/change log, undo and deletion.
- Proactive policy tests: quiet hours, timezone, cooldown, daily caps, deduplication, snooze and global/per-type toggles.

### Integration tests

- Fake STT → orchestrator → fake LLM → fake TTS.
- SQLite repository CRUD và migrations.
- WebSocket event order và cancel/error handling.
- Character pack load và asset lookup.

### End-to-end tests

- Text in → Japanese response → subtitle → mock/real TTS event.
- Voice input tiếng Việt → transcript vi → Japanese output (M2).
- Switch character → persona/voice/assets thay đổi đúng (M6).

### Performance tests

Đo riêng thời gian:

- STT final transcript latency.
- Cloud LLM first-token/full-response latency, quota/error handling and remote/local provider switching.
- TTS first-audio và full synthesis latency.
- Turn end-to-end latency.
- RAM/VRAM peak theo từng model/provider combination.

Kết quả benchmark phải ghi model/version/device/precision và điều kiện mạng. Không tuyên bố realtime nếu chưa có benchmark tái lập.

## 14. Cấu hình và môi trường

Ví dụ cấu hình (không chứa secret):

```yaml
app:
  environment: development
  log_level: INFO

language:
  input: auto
  output: ja-JP
  subtitles: [ja-JP, vi-VN]

inference:
  mode: cloud_first
  allow_local_fallback: false
  automatic_provider_failover: false

ai_access:
  default_mode: byok_direct
  per_capability: {}  # optional explicit overrides: llm, stt, tts, embedding
  enabled_modes: [byok_direct]  # managed_gateway remains disabled until separately implemented
  managed_gateway:
    enabled: false
    base_url: null  # must not be set to an untrusted endpoint
  local:
    enabled: false

providers:
  stt:
    mode: cloud  # local adapter can be selected by the user
    name: mock  # replace with configured cloud provider outside tests
    model: mock-model
  llm:
    mode: cloud
    name: mock  # replace with configured cloud provider outside tests
    model: mock-model
  tts:
    mode: cloud
    name: mock  # replace with configured cloud provider outside tests
    model: mock-model

memory:
  enabled: true
  automatic: true
  background_processing: true
  save_audio: false
  exclude_sensitive_data: true
  user_can_disable: true

proactive:
  enabled: false  # enable in settings after configuring preferences
  timezone: user_local
  quiet_hours: { start: "22:00", end: "08:00" }
  max_messages_per_day: 2
  cooldown_minutes: 240
  inactivity_enabled: false
  reminders_enabled: false

visual:
  default_character: character_01
  transition_ms: 250
```

Config parser phải validate giá trị, hỗ trợ override bằng environment variables và không cho secret xuất hiện trong endpoint public.

## 15. Roadmap kiến trúc

- **M0:** Domain schemas, interfaces, AI access mode enum/router/strategy contracts, fake strategies, app skeleton, config, logging, SQLite foundation, mock providers, health endpoint, tests. No real gateway or provider credentials.
- **M1:** Text conversation, LLM adapter, persona, Japanese-first output, history, TTS adapter, subtitle/visual event.
- **M2:** Audio capture, VAD, STT multilingual, streaming response/audio, transcript correction, interruption cơ bản.
- **M3:** Asset manifest, emotion/scene resolver, transitions/effects, subtitle timing.
- **M4:** Automatic memory extraction/retrieval, filtering, dedup/conflict handling, Adaptive Relationship Profile, memory dashboard, change log/undo/delete/export.
- **M5:** Proactive scheduler, reminders, inactivity triggers, policy controls, quiet hours and rate limits.
- **M6:** Multi-character isolation, plugin capability model, Live2D, packaging, release security/privacy review and optional local inference.
- **M7 (optional future):** Managed AIC Gateway only after separate business/security/legal/operations approval; BYOK may remain alongside it.

## 16. Quy tắc dành cho coding agent

1. Đọc SRS, Architecture Design và ADR hiện có trước khi sửa code.
2. Chỉ làm milestone được giao; không tự ý triển khai các milestone sau.
3. Trước khi code: kiểm tra repository, tóm tắt hiện trạng và viết implementation plan có file list.
4. Nếu thiếu chi tiết không chặn milestone, dùng default trong SRS và ghi lại assumption. Không tự hỏi lại những gì đã được định nghĩa.
5. Không hard-code provider/model/character hoặc access mode; dùng interface/config. Orchestrator chỉ phụ thuộc capability contract.
6. Tách `ProviderAdapter` khỏi `AIAccessStrategy`; không trộn protocol-specific logic với auth/billing. M0 chỉ tạo boundary/mock, M1 triển khai BYOK. Gateway chỉ là future disabled extension; không tự xây server/client thật.
6. Không thêm dependency lớn nếu không có lý do và ADR/ghi chú.
7. Sau mỗi thay đổi: chạy formatter, linter, unit/integration tests phù hợp; báo chính xác lệnh và kết quả.
8. Không nói test pass nếu chưa chạy. Không giả lập kết quả test.
9. Không commit secret, model weights, audio mẫu riêng tư hoặc dữ liệu runtime.
10. Cập nhật README, architecture, ADR và changelog khi có thay đổi liên quan.
11. Không xóa/sửa file người dùng đang có nếu chưa kiểm tra diff và mục đích.
12. Kết thúc milestone bằng báo cáo: đã làm, chưa làm, test, rủi ro, bước tiếp theo.
13. Tuân thủ `docs/AGENT_GITHUB_WORKFLOW_v0.5.md`: branch riêng, PR, CI evidence, risk classification, không direct push main, không bypass branch protection.
14. Không dùng `gh pr merge --admin`; với cùng GitHub identity, AI reviewer comments không được giả nhận là independent approval.

---

## 17. Quyết định triển khai desktop, AI access, runtime và phát triển đã chốt

- Product target: Windows desktop app.
- Window modes: Main Window + Character Overlay; both supported in the same app.
- UI: React + TypeScript inside Tauri 2.
- AI/runtime backend: Python/FastAPI managed sidecar process.
- Local communication: loopback REST + WebSocket with per-launch authentication.
- AI inference: cloud-first provider adapters called by the local backend; local inference is optional and explicitly configured.
- AI access: `byok_direct` là mode mặc định hiện tại; kiến trúc strategy-based, có thể bổ sung `managed_gateway` hoặc `local` mà không sửa Orchestrator. Gateway chưa được triển khai và phải qua ADR/business/security review riêng.
- BYOK credential storage: OS credential vault through `CredentialStore`; never plaintext in DB/config/log/export/Git; no insecure fallback. Gateway account/session credential (future) dùng namespace/lifecycle riêng.
- Provider/access routing: explicit per-capability config; no silent cross-provider, cross-mode or billable failover. UI displays access mode, provider/model, data destination and billing owner label.
- Local ownership: SQLite conversations/memory/assets remain on device by default; only minimal turn context is sent to the selected cloud provider.
- Memory: automatic background pipeline without per-memory confirmation; user can inspect/edit/delete/export/disable.
- Proactive: scheduler + policy engine; global/per-type toggles, quiet hours, cooldown, daily cap and snooze.
- Personality: immutable Core Personality + adaptive Relationship Profile.
- Developer workflow: Google Antigravity `/teamwork` plus Git/GitHub PR workflow; separate from runtime. Teamwork coordinates isolated roles; GitHub branch protection and CI guard `main`; owner approves high-risk changes.
- Shared state: one backend/session manager; both windows are presentation clients.
- Initial delivery order: main window first; overlay window second; then dual-window synchronization and packaging hardening.
- A browser-hosted web edition is not part of the current baseline. Reuse of frontend/backend for a future web edition may be evaluated later through a separate ADR.

**Kết thúc Architecture Design v0.5.**
