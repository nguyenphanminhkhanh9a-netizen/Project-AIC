# PROJECT AIC — SOFTWARE REQUIREMENTS SPECIFICATION

**Mã dự án:** AIC  
**Phiên bản:** 0.5 — Cloud-first AI + Automatic Memory + Proactive Companion  
**Ngày:** 04/11/2026  
**Trạng thái:** Đã chốt desktop dual-window, cloud-first inference, BYOK mặc định trên kiến trúc AI access extensible, automatic memory, proactive companion và GitHub PR workflow có kiểm soát.  
**Đối tượng đọc:** Chủ dự án, AI coding agent, developer, tester

---

## 1. Mục đích tài liệu

Tài liệu này mô tả yêu cầu sản phẩm và tiêu chí nghiệm thu cho Project AIC. Đây là nguồn yêu cầu chuẩn để con người và coding agent cùng hiểu đúng phạm vi, hành vi và giới hạn của hệ thống.

Các tên model, nhà cung cấp API và thư viện trong tài liệu chỉ là **ứng viên kỹ thuật**, không phải ràng buộc vĩnh viễn. Hệ thống phải thay thế được provider thông qua interface mà không phải sửa logic nghiệp vụ.

## 2. Tầm nhìn sản phẩm

Project AIC là một ứng dụng AI Companion cá nhân trên desktop. Người dùng có thể giao tiếp bằng giọng nói hoặc văn bản ở nhiều ngôn ngữ; nhân vật mặc định hiểu đầu vào đa ngôn ngữ và trả lời bằng tiếng Nhật, bằng giọng nói đã được cấu hình. Ứng dụng biểu đạt trạng thái, cảm xúc và bối cảnh bằng bộ ảnh PNG/GIF/WebP, hiệu ứng và phụ đề. Qua thời gian, hệ thống tự động trích xuất và cập nhật memory theo chính sách an toàn; đồng thời điều chỉnh lớp quan hệ/cách tương tác mà không thay đổi Core Personality. Mặc định AI sử dụng cloud API của provider do người dùng tự cấu hình theo mô hình BYOK; xử lý local là phương án tùy chọn. AIC không cung cấp API key dùng chung và không vận hành gateway tính phí thay người dùng trong baseline hiện tại.

AIC không chỉ là chatbot có avatar. Sản phẩm gồm năm năng lực cốt lõi:

1. **Multilingual input:** tiếp nhận tiếng Việt, tiếng Nhật, tiếng Anh và các ngôn ngữ khác mà bộ nhận diện đang cấu hình hỗ trợ.
2. **Japanese-first output:** mặc định câu trả lời được sinh bằng tiếng Nhật; ngôn ngữ phụ đề được cấu hình độc lập.
3. **Expressive character:** hiển thị hình ảnh, biểu cảm, hiệu ứng và lời thoại tương ứng với ngữ cảnh.
4. **Persistent memory:** lưu và truy xuất thông tin dài hạn về người dùng, cuộc trò chuyện và sở thích.
5. **Automatic memory:** tự động trích xuất, chuẩn hóa, lưu, cập nhật và truy xuất memory trong nền; không yêu cầu xác nhận từng memory.
6. **Adaptive relationship:** lớp quan hệ và cách tương tác thay đổi dần theo lịch sử tương tác; Core Personality vẫn cố định.
7. **Proactive companion:** có thể chủ động hỏi thăm, nhắc lịch và mở lời khi người dùng lâu không tương tác, dưới sự điều khiển của lịch, giới hạn tần suất và công tắc riêng.

## 3. Mục tiêu và ngoài phạm vi

### 3.1. Mục tiêu

- Có một ứng dụng desktop cá nhân chạy được trên Windows 11, đóng gói thành bộ cài/ứng dụng Windows (mục tiêu đầu ra `.exe` hoặc installer).
- Hoàn thành một luồng dọc đầu-cuối: nhập văn bản → LLM → câu trả lời tiếng Nhật → TTS → hiển thị nhân vật và phụ đề.
- Mở rộng luồng trên thành: micro → nhận diện đa ngôn ngữ → hội thoại → giọng Nhật → biểu cảm.
- Tách riêng provider, nhân vật, bộ nhớ và visual engine.
- Có thể thay model/API mà không viết lại giao diện hoặc logic hội thoại.
- Cho người dùng kiểm tra, chỉnh sửa, vô hiệu hóa và xóa bộ nhớ.

### 3.2. Ngoài phạm vi MVP

- Huấn luyện một foundation model từ đầu.
- Tự fine-tune hoặc cập nhật trọng số LLM sau mỗi cuộc trò chuyện.
- Điều khiển máy tính, đọc màn hình, gửi tin nhắn hoặc thao tác hệ điều hành một cách tự chủ.
- Tài khoản đa người dùng, đồng bộ cloud memory giữa nhiều thiết bị và ứng dụng mobile. Cloud AI inference vẫn thuộc phạm vi mục tiêu; không đồng nghĩa với cloud sync dữ liệu.
- Phiên bản web độc lập chạy trên trình duyệt như sản phẩm chính.
- Full-duplex voice conversation hoàn chỉnh với ngắt lời tự nhiên ở mọi thời điểm.
- Sinh ảnh nhân vật mới theo thời gian thực.
- Marketplace hoặc chia sẻ công khai voice/character pack.

Các mục này chỉ được xem xét sau khi MVP ổn định và có đánh giá rủi ro riêng.

## 3.3. Nền tảng và mô hình hiển thị đã chốt

- **Sản phẩm:** desktop app cho Windows 11; không phải website và không yêu cầu trình duyệt để sử dụng.
- **Desktop shell:** Tauri 2 là lựa chọn kiến trúc mục tiêu; React + TypeScript xây dựng UI. Python/FastAPI là backend local được desktop shell quản lý như một tiến trình con/sidecar.
- **Hai chế độ hiển thị:** (a) cửa sổ chính đầy đủ tính năng; (b) cửa sổ nhân vật overlay nổi trên desktop. Cả hai là hai cửa sổ của cùng một ứng dụng.
- **Trạng thái dùng chung:** hội thoại, nhân vật, cảm xúc, phụ đề, trạng thái nghe/nói và bộ nhớ do backend quản lý; UI không giữ bản sao nguồn sự thật.
- **Phạm vi hiển thị:** bản đầu hỗ trợ chuyển đổi giữa hai chế độ. Việc mở đồng thời cả hai cửa sổ là khả năng được thiết kế hỗ trợ, nhưng không bắt buộc cho MVP đầu tiên.
- **Không mặc định:** không tự động click-through, không tự khởi động cùng Windows và không ẩn vào system tray nếu chưa có cài đặt/đồng ý rõ ràng.


### 3.4. Mô hình truy cập AI — BYOK mặc định, hỗ trợ mở rộng sang Gateway

- **BYOK (`byok_direct`) là chế độ mặc định hiện tại:** người dùng tự tạo tài khoản/API key tại provider và nhập key vào AIC. Local Python sidecar gọi trực tiếp cloud API qua HTTPS.
- **BYOK không phải ràng buộc kiến trúc:** AI Orchestrator chỉ gọi một hợp đồng inference/capability nội bộ; không được biết API key được cấp bởi người dùng, AIC Gateway hay local runtime.
- AIC phải có một `AIAccessRouter`/`AccessStrategyRegistry` để chọn đường thực thi theo capability (LLM/STT/TTS/embedding) và cấu hình người dùng. Giá trị mode được chuẩn hóa: `byok_direct` (mặc định), `managed_gateway` (tương lai, tắt mặc định) và `local` (tùy chọn khi có adapter phù hợp).
- Tách biệt hai trách nhiệm: `ProviderAdapter` chuẩn hóa giao thức/model của nhà cung cấp; `AIAccessStrategy` quyết định đường truy cập và cách xác thực/ủy quyền. Không trộn logic credential/billing vào Orchestrator hoặc domain model.
- Với `byok_direct`, API key lưu trong OS credential vault thông qua `CredentialStore`. Không plaintext trong SQLite, file cấu hình, `.env`, log, crash report, export hoặc Git. Không plaintext fallback.
- Với `managed_gateway` trong tương lai, desktop client chỉ dùng `GatewayClient`/account session credential riêng; API key upstream của các model nằm phía server/gateway, tuyệt đối không chuyển provider master key xuống desktop. Gateway phải có ADR, threat model, account authentication, usage metering, quota/billing, abuse prevention, privacy/retention policy và vận hành server riêng trước khi bật.
- Với `local`, request tới model/runtime local đã được người dùng cài và cấu hình. Không tự tải model lớn hoặc tự chuyển sang local khi chưa được bật.
- Có thể cấu hình mode theo từng capability trong tương lai, ví dụ LLM dùng BYOK còn TTS dùng Gateway; tuy nhiên mỗi route phải được người dùng chọn rõ, hiển thị provider/model/data destination/cost owner và không tự động failover.
- **Phạm vi baseline hiện tại:** chỉ triển khai BYOK; Gateway chỉ được thiết kế để có thể bổ sung sau này. M0 tạo interface/config boundary/mock tests; M1 triển khai BYOK thật. Không xây AIC Gateway hoặc central billing trong các milestone hiện tại.
- Trong BYOK, người dùng thanh toán trực tiếp cho provider. Trong Gateway mode tương lai, billing/usage do dịch vụ AIC quản lý theo chính sách sẽ được công bố riêng. AIC không được giả định API miễn phí hoặc không giới hạn.

## 4. Người dùng và giả định ban đầu

### 4.1. Người dùng mục tiêu

- Một người dùng chính, sử dụng ứng dụng trên máy tính cá nhân.
- Người dùng có thể nói tiếng Việt hoặc ngôn ngữ khác do STT hỗ trợ.
- Người dùng muốn nhân vật nói tiếng Nhật mặc định, có phụ đề tiếng Nhật và tùy chọn bản dịch tiếng Việt.
- Người dùng cung cấp hoặc lựa chọn asset hình ảnh và mẫu giọng nói mà họ có quyền sử dụng.

### 4.2. Môi trường triển khai tham chiếu

- Windows 11.
- CPU Intel Core i7-13620H.
- GPU NVIDIA RTX 4050 Laptop 6GB VRAM.
- RAM 16GB.
- Kết nối Internet là cần thiết cho cloud AI inference mặc định. STT/TTS ưu tiên provider cloud khi phù hợp; local provider là lựa chọn thay thế tùy cấu hình.

Đây chỉ là môi trường tham chiếu kiểm thử desktop. Người dùng cuối không cần GPU mạnh để chạy LLM vì inference mặc định thực hiện qua cloud API. Ứng dụng vẫn phải cho phép provider local tùy chọn, nhưng không được yêu cầu người dùng tải/chạy model lớn để có trải nghiệm mặc định.

## 5. Quy tắc ngôn ngữ

### 5.1. Nguyên tắc bắt buộc

- `input_language` và `output_language` là hai cấu hình độc lập.
- `input_language` mặc định là `auto`.
- `output_language` mặc định là `ja-JP`.
- `subtitle_languages` mặc định gồm `ja-JP`; người dùng có thể bật thêm `vi-VN`.
- LLM phải hiểu nội dung gốc của người dùng, không bắt buộc dịch đầu vào sang tiếng Nhật trước khi hiểu.
- Câu trả lời dùng để TTS phải là tiếng Nhật hợp lệ, trừ khi người dùng chủ động đổi cài đặt.
- Khi ASR không nhận diện đủ tin cậy, hệ thống phải cho phép xem/sửa transcript hoặc chuyển sang nhập văn bản.

### 5.2. Ví dụ hành vi

Người dùng nói: “Hôm nay tôi rất mệt.”  
Hệ thống nhận diện: `vi-VN`.  
LLM hiểu nội dung và ngữ cảnh bằng ngôn ngữ nội bộ phù hợp.  
Nhân vật trả lời bằng tiếng Nhật.  
UI hiển thị phụ đề Nhật; nếu bật dịch, hiển thị thêm phụ đề Việt.  
TTS đọc phần tiếng Nhật, không đọc phần dịch tiếng Việt.

### 5.3. Giới hạn

“Ngôn ngữ bất kỳ” được hiểu là ngôn ngữ nằm trong phạm vi hỗ trợ thực tế của STT/LLM được cấu hình. Không được quảng bá rằng hệ thống hiểu mọi ngôn ngữ nếu chưa kiểm thử. Luôn có đường lui nhập văn bản.

## 6. Yêu cầu chức năng

Mức ưu tiên: **P0** = bắt buộc cho MVP; **P1** = quan trọng sau MVP; **P2** = mở rộng.

| ID | Yêu cầu | Ưu tiên | Tiêu chí nghiệm thu tóm tắt |
|---|---|---:|---|
| FR-01 | Nhập văn bản | P0 | Người dùng gửi text và nhận phản hồi từ nhân vật. |
| FR-02 | Nhập âm thanh từ microphone | P1 | Có quyền truy cập mic, trạng thái ghi âm và xử lý lỗi thiết bị. |
| FR-03 | Nhận diện ngôn ngữ tự động | P1 | Transcript có mã ngôn ngữ và confidence nếu provider hỗ trợ. |
| FR-04 | STT đa ngôn ngữ | P1 | Có thể nhận diện các ngôn ngữ được provider công bố hỗ trợ; có fallback text. |
| FR-05 | Đầu ra tiếng Nhật mặc định | P0 | Mọi phản hồi TTS mặc định sử dụng nội dung `ja-JP`. |
| FR-06 | Phụ đề tiếng Nhật | P0 | Hiển thị chính xác văn bản tiếng Nhật đã sinh. |
| FR-07 | Phụ đề dịch tùy chọn | P1 | Có thể bật/tắt phụ đề tiếng Việt mà không đổi tiếng TTS. |
| FR-08 | TTS qua provider adapter | P0 | Sinh được audio từ văn bản tiếng Nhật; provider có thể thay thế. |
| FR-09 | Chọn voice profile | P1 | Chọn, thử, đổi và lưu voice profile theo nhân vật. |
| FR-10 | Cấu hình tính cách gốc | P0 | Nhân vật có persona prompt/config độc lập với code. |
| FR-11 | Lưu lịch sử hội thoại | P0 | Tin nhắn có thời gian, role, conversation ID và metadata. |
| FR-12 | Short-term context | P0 | Hội thoại hiện tại được đưa vào context theo giới hạn cấu hình. |
| FR-13 | Automatic long-term memory | P1 | Hệ thống tự động trích xuất, chuẩn hóa, lưu, cập nhật và truy xuất memory ở background; không hỏi xác nhận từng mục. |
| FR-14 | Memory management | P1 | Người dùng có thể xem, sửa, xóa, export và tắt/bật memory bất cứ lúc nào. |
| FR-15 | Adaptive relationship profile | P1 | Hệ thống tự động cập nhật lớp quan hệ/preference dựa trên bằng chứng; giữ lịch sử thay đổi và không sửa Core Personality. |
| FR-16 | Không tự ghi đè Core Personality | P0 | Memory chỉ điều chỉnh lớp thích nghi, không sửa bản sắc gốc. |
| FR-17 | Visual state | P0 | UI hiển thị trạng thái idle/listening/thinking/speaking/error. |
| FR-18 | Emotion mapping | P1 | LLM trả metadata cảm xúc theo schema; visual engine chọn asset hợp lệ. |
| FR-19 | Asset manifest | P0 | Mỗi asset có ID, đường dẫn, tags, emotion/state và fallback. |
| FR-20 | Hiệu ứng và caption | P1 | Có thể hiển thị hiệu ứng và lời thoại chạy phía dưới nhân vật. |
| FR-21 | Tùy chỉnh character pack | P1 | Thay asset/voice/persona bằng cấu hình, không sửa logic core. |
| FR-22 | Provider settings | P0 | Chọn provider, model, endpoint và cấu hình qua settings/env. |
| FR-23 | Text fallback | P0 | Ứng dụng vẫn trò chuyện được khi mic/STT/TTS lỗi. |
| FR-24 | Health/status | P0 | Hiển thị trạng thái backend, provider và lỗi có thể hành động. |
| FR-25 | Export/delete data | P1 | Người dùng xuất và xóa dữ liệu cá nhân, memory và lịch sử. |
| FR-26 | Cửa sổ ứng dụng chính | P0 | Có giao diện chat, cài đặt, lịch sử và quản lý bộ nhớ trong cửa sổ desktop. |
| FR-27 | Character overlay | P1 | Có cửa sổ nhân vật nổi, nền trong suốt khi khả thi, có thể bật/tắt Always on Top. |
| FR-28 | Chuyển chế độ hiển thị | P0 | Người dùng chuyển giữa cửa sổ chính và overlay mà không tạo phiên hội thoại mới hoặc mất trạng thái. |
| FR-29 | Đồng bộ trạng thái hiển thị | P1 | Cửa sổ chính và overlay dùng chung character state, subtitle, audio state và conversation session. |
| FR-30 | Điều khiển overlay | P1 | Có thao tác ẩn/hiện, kéo vị trí, thay kích thước và mở lại cửa sổ chính. |
| FR-31 | Cloud-first AI provider | P0 | LLM mặc định chạy qua cloud API adapter; provider/model có thể đổi trong settings mà không sửa domain logic. |
| FR-32 | Provider data transparency | P0 | Settings hiển thị provider, model, remote/local mode và loại dữ liệu được gửi tới provider; không đưa API key xuống frontend. |
| FR-33 | Proactive conversation | P1 | Nhân vật có thể chủ động hỏi thăm/mở lời theo trigger được bật, nhưng phải tuân thủ quiet hours, cooldown và giới hạn tần suất. |
| FR-34 | Proactive reminders | P1 | Có thể tạo/hiển thị lời nhắc theo lịch hoặc thời điểm do người dùng cấu hình; hỗ trợ hoàn tất, snooze và tắt từng loại. |
| FR-35 | Proactive controls | P1 | Có công tắc tổng, công tắc theo loại, quiet hours, timezone, cooldown và mức tối đa thông báo. |
| FR-36 | Automatic memory lifecycle | P1 | Memory pipeline chạy nền không cần duyệt từng mục; tự lọc dữ liệu không phù hợp, xử lý trùng/mâu thuẫn và ghi lịch sử thay đổi. |
| FR-37 | BYOK provider credentials | P0 | Người dùng nhập key do chính họ tạo cho provider đã chọn; AIC không cấp key dùng chung. |
| FR-38 | Secure credential storage | P0 | Key được lưu qua OS credential vault; không lưu plaintext trong DB/config/log/export hoặc frontend persistence. |
| FR-39 | Credential lifecycle | P1 | Có thể test connection, thay key, xóa key và xem provider credential status mà không lộ secret. |
| FR-40 | Provider transparency | P0 | Hiển thị provider/model/capability, remote processing notice và cảnh báo chi phí/quota khi provider cung cấp thông tin. |
| FR-41 | Explicit provider routing | P0 | Không tự động failover sang provider hoặc model có thể phát sinh chi phí/định tuyến dữ liệu khác nếu chưa được cấu hình rõ. |
| FR-42 | AI access strategy abstraction | P0 | Orchestrator gọi hợp đồng inference trung lập; route được giải quyết qua AccessStrategyRegistry, không phụ thuộc trực tiếp BYOK/Gateway/local. M0 có contract và mock tests. |
| FR-43 | Managed Gateway compatibility | P2 | Kiến trúc cho phép bổ sung `managed_gateway` route và account session credential riêng; chưa triển khai Gateway server/client production trong baseline. |
| FR-44 | Per-capability route configuration | P1 | Có thể cấu hình access mode/provider/model theo LLM, STT, TTS và embedding; mỗi route minh bạch và không tự failover. |

## 7. Yêu cầu phi chức năng

| ID | Nhóm | Yêu cầu |
|---|---|---|
| NFR-01 | Khả năng mở rộng | Provider STT/LLM/TTS/embedding phải được thay thế qua interface ổn định. |
| NFR-02 | Bảo trì | Modular monolith; module có trách nhiệm rõ; tránh circular imports. |
| NFR-03 | Hiệu năng | Đo riêng STT latency, LLM first-token latency, TTS first-audio latency và end-to-end latency. Không hard-code một SLA trước khi benchmark trên máy tham chiếu. |
| NFR-04 | Trải nghiệm | UI phải hiển thị trạng thái đang nghe, đang xử lý, đang nói và lỗi; không để người dùng tưởng ứng dụng bị treo. |
| NFR-05 | Độ tin cậy | Lỗi của một provider không được làm sập toàn bộ backend; cần timeout, retry có giới hạn và fallback. |
| NFR-06 | Riêng tư | Audio không được lưu lâu dài mặc định; chỉ lưu khi người dùng bật tùy chọn rõ ràng. Memory được xử lý tự động nhưng phải có cơ chế xem/sửa/xóa/tắt. |
| NFR-07 | Bảo mật | API key không được commit vào Git hoặc gửi về frontend; dùng environment/local secret store. |
| NFR-08 | Quyền kiểm soát | Người dùng có quyền xem, sửa, xóa, export và tắt memory. |
| NFR-09 | Tài nguyên | Cloud inference là mặc định để không phụ thuộc GPU; local inference là tùy chọn và phải có giới hạn CPU/GPU/RAM. |
| NFR-10 | Khả năng kiểm thử | Mọi provider phải có fake/mock adapter để chạy test không cần API key hoặc model thật. |
| NFR-11 | Khả năng quan sát | Log có correlation ID; không ghi API key, audio thô hoặc dữ liệu nhạy cảm vào log mặc định. |
| NFR-12 | Tương thích | UI và backend giao tiếp bằng API/event có version. |
| NFR-13 | Khôi phục | Database có backup/export và migration có phiên bản. |
| NFR-14 | Khả năng tiếp cận | Hỗ trợ điều khiển bằng bàn phím, phụ đề rõ ràng, trạng thái không chỉ biểu diễn bằng màu. |
| NFR-15 | Desktop lifecycle | Backend local phải được ứng dụng desktop khởi chạy, giám sát và dừng an toàn; không yêu cầu người dùng tự mở terminal. |
| NFR-16 | Local IPC security | API local chỉ bind loopback, dùng token phiên ngẫu nhiên, giới hạn origin và không công khai cổng ra mạng LAN. |
| NFR-17 | Multi-window consistency | Các cửa sổ không được tạo hai orchestrator hoặc hai phiên hội thoại độc lập cho cùng một người dùng. |
| NFR-18 | Overlay behavior | Overlay phải có cơ chế tránh chặn thao tác chuột ngoài ý muốn; hỗ trợ click-through hoặc chế độ tương tác nếu nền tảng cho phép. |
| NFR-19 | Cloud resilience | Timeout, retry giới hạn, quota/error handling và trạng thái offline phải rõ; không âm thầm chuyển sang provider tính phí khác. |
| NFR-20 | Memory safety | Không lưu credentials, password, payment card, API key hoặc dữ liệu nhạy cảm/định danh có rủi ro cao vào memory tự động. |
| NFR-21 | Proactive restraint | Không gửi thông báo ngoài quiet hours; không lặp thông báo trùng; tuân thủ cooldown và giới hạn đã cấu hình. |
| NFR-22 | Secret-at-rest | Provider credentials phải dùng OS credential vault; không plaintext fallback. |
| NFR-23 | Secret minimization | API key chỉ tồn tại trong bộ nhớ backend trong thời gian cần thiết; tuyệt đối không log hoặc gửi về UI sau thao tác lưu. |
| NFR-24 | BYOK data transparency | Trước khi gọi cloud provider, người dùng phải biết provider/model và nhóm dữ liệu được gửi; API key không đồng nghĩa với quyền chia sẻ toàn bộ local database. |
| NFR-25 | Cost predictability | Có timeout, token/request budget khi provider hỗ trợ; không tự phát sinh request nền hoặc đổi provider ngoài policy người dùng. |
| NFR-26 | Agent change traceability | Mọi thay đổi code phải có branch/commit/PR và bằng chứng test; không push trực tiếp vào `main`. |
| NFR-27 | Merge governance | Merge chỉ khi PR checks đạt, comment được xử lý và mức rủi ro phù hợp; agent không được bypass protection hoặc dùng quyền admin để ép merge. |
| NFR-28 | AI access extensibility | Có thể thêm access mode mới qua strategy/adapter mà không sửa Conversation Orchestrator, prompt composer hoặc UI chat flow. |
| NFR-29 | Credential domain separation | BYOK provider keys và Gateway account/session credentials là hai loại secret khác nhau, có storage scope, rotation và deletion policy riêng. |
| NFR-30 | Gateway isolation | Gateway mode (khi được triển khai) không được nhận hoặc lưu BYOK provider keys; không được dùng chung secret namespace hoặc fallback credential. |

## 8. Luồng sử dụng chính

### UC-01 — Trò chuyện bằng văn bản

1. Người dùng chọn nhân vật trong cửa sổ chính hoặc tiếp tục từ overlay.
2. Người dùng nhập tin nhắn.
3. Orchestrator lấy persona, short-term context và memory liên quan.
4. LLM tạo response tiếng Nhật theo schema.
5. UI hiển thị câu trả lời, cảm xúc và trạng thái nhân vật.
6. TTS phát âm thanh nếu được bật.
7. Tin nhắn được lưu vào lịch sử; memory extraction chạy theo chính sách riêng.

### UC-02 — Trò chuyện bằng giọng nói

1. Người dùng cấp quyền microphone và nhấn giữ/nút ghi âm hoặc bật VAD.
2. Audio được phân đoạn và chuyển tới STT provider.
3. STT trả transcript, detected language và confidence.
4. Người dùng có thể sửa transcript nếu cần.
5. Orchestrator xử lý giống UC-01.
6. TTS đọc tiếng Nhật; UI hiển thị subtitle theo chunk/timestamp nếu có.

### UC-03 — Automatic memory learning

1. Sau mỗi turn hoặc theo batch, background worker phân tích hội thoại theo chính sách memory đã bật.
2. Extractor chỉ tạo memory từ thông tin có giá trị lâu dài; gắn nguồn, confidence, importance, sensitivity và thời điểm.
3. Pipeline tự kiểm tra trùng lặp, mâu thuẫn, độ tin cậy và dữ liệu bị cấm lưu. Không hỏi người dùng xác nhận từng mục.
4. Memory đủ điều kiện được tự động lưu/cập nhật; memory không đủ tin cậy hoặc mâu thuẫn chưa giải quyết không được áp dụng vào retrieval cho đến khi có bằng chứng tốt hơn.
5. Mọi thay đổi có version/source trong change log; memory bị thay thế có thể được khôi phục theo chính sách lưu trữ.
6. Người dùng có thể mở Memory Dashboard để xem, sửa, xóa, export hoặc tắt toàn bộ memory. Thay đổi thủ công của người dùng được ưu tiên hơn suy luận tự động.
7. Adaptive Relationship Profile được cập nhật riêng; Core Personality không bị sửa.


### UC-04 — Chuyển nhân vật

1. Người dùng chọn character pack khác.
2. Hệ thống nạp persona, voice profile, asset manifest và visual settings của pack.
3. Bộ nhớ cá nhân toàn cục chỉ được dùng theo quyền đã cấp; memory riêng của nhân vật không trộn lẫn nếu chưa bật.
4. Hội thoại tiếp tục theo cấu hình mới.

### UC-05 — Chuyển giữa cửa sổ chính và overlay

1. Người dùng chọn `Show as Overlay` từ cửa sổ chính hoặc mở cửa sổ chính từ overlay.
2. Desktop shell hiển thị cửa sổ tương ứng; backend và conversation session hiện tại vẫn chạy duy nhất.
3. Cửa sổ đích đăng ký nhận các event hiện tại (visual state, subtitle, audio state).
4. Nếu cả hai cửa sổ cùng mở, chúng hiển thị cùng một trạng thái; chỉ một nơi được phép phát audio cho một turn.
5. Người dùng có thể ẩn overlay mà không đóng ứng dụng hoặc dừng backend.

### UC-06 — Chủ động hỏi thăm và nhắc lịch

1. Scheduler nhận trigger từ lịch nhắc hoặc điều kiện inactivity được người dùng cho phép.
2. Proactive Policy Engine kiểm tra công tắc tổng/theo loại, quiet hours, timezone, cooldown, daily cap, trạng thái app và snooze.
3. Nếu bị chặn, trigger được hoãn/bỏ theo policy; không gọi LLM và không phát thông báo.
4. Nếu được phép, AIC tạo nội dung ngắn qua provider đã cấu hình và hiển thị notification/character message.
5. Người dùng có thể phản hồi, snooze, hoàn tất reminder hoặc tắt loại proactive tương ứng.
6. Trong baseline local-only, khi app đã thoát hoàn toàn hoặc máy đang tắt/ngủ, AIC không gửi push notification từ cloud. Reminder đến hạn được lưu local và xử lý theo chính sách khi app mở lại; notification khi app không có cửa sổ chỉ hoạt động nếu người dùng bật rõ chế độ background/tray/autostart tương ứng.


### UC-07 — Thiết lập BYOK cho provider cloud

1. Người dùng mở Settings → AI Providers và chọn capability (LLM, STT, TTS hoặc embeddings) cùng provider/model.
2. AIC hiển thị hướng dẫn đăng ký/lấy API key từ website chính thức của provider và nhắc người dùng xem giá, quota, data retention/usage policy.
3. Người dùng nhập key vào trường secret; frontend chỉ giữ nội dung tạm trong lúc submit và không lưu vào browser/local storage/log.
4. Local backend kiểm tra định dạng/kết nối theo cách không in key ra output, rồi lưu qua OS credential vault.
5. AIC lưu metadata không nhạy cảm (provider ID, model ID, capability, credential reference ID, created/updated time) trong settings/database.
6. Settings hiển thị trạng thái `configured`, `connection_failed`, `missing` hoặc `needs_reauth`, không hiển thị lại key đầy đủ.
7. Người dùng có thể thay hoặc xóa key. Xóa key phải làm provider tương ứng ngừng hoạt động, không tự chuyển sang provider khác.
8. Khi gửi request, backend lấy key từ CredentialStore và gửi trực tiếp tới provider qua HTTPS; conversation/memory database vẫn local theo mặc định.


## 9. Quy tắc hình ảnh và biểu cảm

### 9.1. Trạng thái hiển thị cơ bản

- `idle`: nhân vật chờ.
- `listening`: đang nghe người dùng.
- `thinking`: đang xử lý.
- `speaking`: đang phát lời thoại.
- `error`: cần báo lỗi hoặc fallback.

### 9.2. Cảm xúc khởi đầu

`neutral`, `happy`, `sad`, `angry`, `shy`, `embarrassed`, `surprised`, `confused`, `excited`, `sleepy`, `comforting`.

### 9.3. Bối cảnh khởi đầu

`default`, `morning`, `night`, `studying`, `relaxing`, `celebration`, `comfort`.

### 9.4. Nguyên tắc chọn asset

- LLM chỉ được trả emotion/scene/action ID thuộc schema; không được tự tạo đường dẫn file.
- Visual Engine kiểm tra asset tồn tại trong manifest trước khi hiển thị.
- Phải có fallback: emotion không có asset → neutral; scene không có background → default; effect không hợp lệ → bỏ qua.
- Tránh đổi hình quá nhanh; cần debounce/minimum display duration và transition.
- GIF/PNG/WebP dùng cho MVP. Lip-sync chính xác chưa phải tiêu chí MVP; có thể dùng mouth overlays/sprite states đơn giản. Live2D là hướng nâng cấp.
- Hiệu ứng nên chủ yếu được dựng bằng CSS/canvas/UI layer để có thể bật/tắt độc lập với ảnh nhân vật.

## 10. Bộ nhớ tự động, thích nghi và quyền kiểm soát

### 10.1. Các lớp memory và personality

| Lớp | Nội dung | Vòng đời |
|---|---|---|
| Working/short-term | Context cuộc trò chuyện hiện tại | Theo phiên/context window |
| Conversation history | Nội dung hội thoại | Lưu local theo cài đặt; có thể export/xóa |
| Semantic/profile memory | Sở thích, mục tiêu, thông tin ổn định hữu ích | Tự động cập nhật; người dùng có thể sửa/xóa |
| Episodic memory | Sự kiện/câu chuyện đáng nhớ có nguồn và thời điểm | Có thể hết hạn, tóm tắt hoặc archive |
| Adaptive Relationship Profile | Mức thân thiết, cách xưng hô, phong cách giao tiếp, preference | Phát triển dần theo tương tác và feedback |
| Core Personality | Giá trị, temperament, giọng điệu nền, nguyên tắc ứng xử | Cố định theo version; chỉ thay đổi qua character configuration có chủ đích |

### 10.2. Memory record tối thiểu

Mỗi memory record cần có:

- `id`, `user_id`, `character_id` hoặc `global`, `memory_type`, `content`.
- `source_message_ids` hoặc reference tới sự kiện nguồn; không lưu nguyên văn hội thoại nhiều hơn mức cần thiết.
- `confidence`, `importance`, `sensitivity`, `created_at`, `updated_at`, `last_accessed_at`.
- `status`: `active`, `superseded`, `archived`, `deleted`.
- `expires_at` (nullable), `version`, `updated_by` (`automation` hoặc `user`).
- Metadata giải thích lý do tạo/cập nhật và liên kết tới `memory_change_log`.

### 10.3. Quy trình tự động 100% ở cấp từng memory

- Memory extraction, deduplication, confidence scoring, conflict checks, store/update, indexing và retrieval chạy nền; không yêu cầu người dùng phê duyệt từng mục.
- Ưu tiên thông tin người dùng chủ động nói rõ, preference lặp lại, mục tiêu dài hạn và sự kiện có ích cho tương tác tương lai.
- Tự động cập nhật memory khi thông tin mới có bằng chứng tốt hơn; không âm thầm ghi đè memory có độ tin cậy cao bằng dữ liệu yếu hơn.
- Memory confidence thấp, không rõ chủ thể hoặc mâu thuẫn chưa giải quyết phải được giữ ngoài retrieval hoặc đánh dấu unresolved; không hỏi người dùng liên tục để xác nhận.
- Thay đổi tự động phải có nguồn, timestamp, phiên bản và khả năng undo/restore phù hợp.
- Người dùng có quyền xem, sửa, xóa, export và tắt/bật memory bất cứ lúc nào. Memory đã xóa phải bị loại khỏi retrieval ngay.
- Bộ lọc tự động loại credentials, password, API key, payment data và dữ liệu cá nhân nhạy cảm/rủi ro cao khỏi memory dài hạn. Không suy đoán thuộc tính nhạy cảm.
- Việc memory chạy tự động không đồng nghĩa với việc gửi mọi dữ liệu lên cloud: chỉ context tối thiểu cần thiết được gửi tới provider đã cấu hình; ứng dụng phải giải thích rõ remote processing trong Settings/Onboarding.
- Không tự huấn luyện hoặc cập nhật trọng số LLM. Thích nghi bằng retrieval, profile và prompt composition.

### 10.4. Core Personality và Adaptive Relationship Profile

- Core Personality định nghĩa bản sắc nền: giá trị, temperament, giới hạn, chất giọng và nguyên tắc ứng xử. Runtime memory không được sửa lớp này.
- Adaptive Relationship Profile định nghĩa cách nhân vật tương tác với người dùng cụ thể: độ thân thiết, mức chủ động, cách xưng hô, chủ đề quan tâm và nhịp hội thoại.
- Profile thích nghi tự động nhưng có giới hạn, có version/change log và chịu ưu tiên từ thiết lập trực tiếp của người dùng.
- Khi người dùng chỉnh một preference trong Settings, lựa chọn thủ công có ưu tiên cao hơn suy luận của AI.

## 11. Tiêu chí nghiệm thu MVP

MVP được xem là đạt khi:

1. Ứng dụng desktop được đóng gói và mở được trên Windows 11; người dùng không cần tự khởi chạy backend bằng terminal.
2. Người dùng gửi text và nhận phản hồi tiếng Nhật.
3. Phản hồi tiếng Nhật xuất hiện dưới dạng subtitle.
4. TTS adapter tạo được file/stream audio tiếng Nhật qua ít nhất một provider thử nghiệm.
5. Nhân vật hiển thị trạng thái idle/thinking/speaking và chọn asset theo manifest.
6. Lịch sử hội thoại được lưu vào SQLite.
7. Có cấu hình persona, output language, subtitle language và provider qua Settings.
8. Có BYOK flow cho ít nhất một LLM provider thử nghiệm; API key được lưu trong OS credential vault, không xuất hiện trong frontend persistence, SQLite, log hoặc Git.
9. Có mock provider để chạy test mà không cần API key.
10. Có AI access abstraction/route resolver trung lập với `byok_direct`, `managed_gateway` và `local` mode; M0 dùng fake/mock strategy, không gọi dịch vụ thật.
11. Test chứng minh Orchestrator không đọc API key hoặc phụ thuộc mode cụ thể; unsupported/disabled mode phải trả lỗi rõ.
12. Gateway mode bị disable trong baseline và không có endpoint/service/account/billing thật được tạo.
13. Không có secret trong source code/repository.
14. Có README hướng dẫn cài đặt, chạy, test và cấu hình provider.
15. Cửa sổ chính và overlay đều mở được; chuyển qua lại không mất hội thoại.
16. Overlay có thể bật/tắt Always on Top, kéo vị trí và ẩn/hiện.
17. Đóng cửa sổ chính theo hành vi đã định (ẩn xuống tray hoặc thoát ứng dụng) không làm backend bị treo mồ côi.

MVP không được xem là hoàn tất chỉ vì giao diện đẹp hoặc demo chạy một lần; phải có test và hướng dẫn tái lập.

## 12. Roadmap và cổng kiểm soát

| Milestone | Phạm vi | Điều kiện chuyển giai đoạn |
|---|---|---|
| M0 — Foundation | Repo, cấu trúc module, config, logging, schemas, health, mock providers, AI access strategy boundary, tests, docs | Project chạy được; access route mocks hoạt động; không cần API key hoặc Gateway thật. |
| M1 — Text Companion + BYOK | Chat text, BYOK setup + OS credential storage, LLM adapter, Japanese output, persona, SQLite history, TTS adapter, subtitle/visual baseline | Đạt tiêu chí MVP mục 11. |
| M2 — Voice I/O | Mic, VAD/recording, multilingual STT, transcript correction, streaming TTS, interruption cơ bản | Test tiếng Việt/Anh/Nhật; có fallback và latency report. |
| M3 — Expressive Visuals | Asset manifest, emotion engine, scenes, effects, transitions, subtitle timing | Bộ test emotion→asset và fallback pass. |
| M4 — Automatic Memory & Adaptation | Background extraction, dedup/conflict/sensitivity filtering, auto-upsert, retrieval, Adaptive Relationship Profile, Memory Dashboard | Không cần duyệt từng mục; test memory precision, edit/delete/export/undo và tắt memory. |
| M5 — Proactive Companion | Scheduler, inactivity triggers, reminders, notification policy, quiet hours, cooldown và per-type controls | Trigger được kiểm thử; không gửi trong quiet hours/vượt quota; snooze/disable hoạt động. |
| M6 — Expansion & Release | Multi-character, plugin capability model, Live2D, optional local inference, installer, release security/privacy review và hardening | Có ADR, license/privacy review, benchmark, packaging và lifecycle ổn định. |

**Quy tắc:** mỗi milestone phải hoàn thành, test, cập nhật tài liệu và tạo checkpoint/commit trước khi Agent bắt đầu milestone kế tiếp.

**Hướng mở rộng sau release:** có thể mở một milestone riêng cho AIC Managed Gateway (tạm gọi M7), gồm account/auth, gateway service, usage metering, quotas/billing, abuse controls, upstream secret management và data-retention policy. Đây không phải cam kết triển khai; cần Owner phê duyệt business case và ADR trước. BYOK vẫn có thể tiếp tục là mode miễn phí/tự quản lý song song.

## 13. Rủi ro và biện pháp

| Rủi ro | Tác động | Giảm thiểu |
|---|---|---|
| Model/API thay đổi hoặc hết quota | Mất khả năng chat | Provider adapter, mock, fallback, quota monitor. |
| RTX 4050 6GB không đủ chạy nhiều model | Chậm/OOM | Tải tuần tự, CPU fallback, benchmark, cấu hình model nhỏ. |
| Nhận diện sai ngôn ngữ | Hiểu sai nội dung | Confidence threshold, sửa transcript, text fallback. |
| TTS tiếng Nhật không tự nhiên | Trải nghiệm kém | So sánh provider/voice, test native sample, cho phép thay voice. |
| Asset không khớp ngữ cảnh | Biểu cảm sai | Emotion schema, rule mapping, fallback, giới hạn cường độ. |
| Memory lưu sai hoặc quá nhiều | Cá nhân hóa sai | Tự động confidence filter, nguồn bằng chứng, conflict policy, change log, undo và user edit/delete; không cần duyệt từng mục. |
| Rò rỉ API key hoặc audio | Rủi ro riêng tư | Secret handling, local storage, data minimization, provider transparency, không log audio và không nhúng shared API key trong desktop binary. |
| Quyền sử dụng mẫu giọng/ảnh không rõ | Rủi ro pháp lý/nền tảng | Chỉ dùng mẫu có quyền sử dụng/đồng ý; metadata nguồn và license. |
| Agent tạo code vượt phạm vi | Khó debug | Dùng Antigravity Teamwork theo pha scope → approve → execute; phân quyền sở hữu file và yêu cầu auditor độc lập. |
| Proactive làm phiền | Người dùng tắt ứng dụng | Global/per-type toggle, quiet hours, cooldown, daily cap, snooze và trạng thái background rõ ràng. |
| Phụ thuộc cloud/quota/network | Mất khả năng inference tạm thời | Timeout/retry, quota visibility, provider switch có chủ đích; local fallback chỉ khi người dùng cấu hình. |
| Người dùng làm lộ API key | Người khác dùng key gây phát sinh chi phí | OS credential vault, key không xuất hiện trong log/export, hướng dẫn rotate/revoke key khi nghi ngờ lộ. |
| Provider lưu/ xử lý dữ liệu theo chính sách riêng | Rủi ro privacy ngoài kiểm soát AIC | Hiển thị provider/data disclosure; chỉ gửi context tối thiểu; người dùng tự xem điều khoản provider. |
| Agent tự merge code lỗi | Main branch bị hỏng | Branch protection, CI required checks, PR review, phân loại rủi ro và human merge gate cho thay đổi quan trọng. |
| Nhiều agent dùng chung workspace/branch | Ghi đè file hoặc race condition | Antigravity isolated workspaces, file ownership độc quyền, coordinator integration và branch riêng theo task. |
| Agent review cùng GitHub identity với PR author | Review không đáp ứng required approval của GitHub | AI review là advisory; required approval phải đến từ reviewer độc lập có quyền phù hợp hoặc do owner cấu hình. |

## 14. Các quyết định mặc định của bản 0.5

Để tránh chặn tiến độ vì các chi tiết chưa chốt, tạm dùng các mặc định sau:

- Ứng dụng desktop cá nhân, single-user, Windows 11; không xây web app làm sản phẩm chính.
- Desktop shell dự kiến dùng Tauri 2 + React/TypeScript; Python backend chạy local như managed sidecar process.
- Có cửa sổ chính và cửa sổ overlay; người dùng có thể chuyển đổi hoặc mở đồng thời theo cấu hình. Hai cửa sổ dùng chung một backend/session.
- Input language: auto; text input luôn khả dụng.
- Output language: Japanese (`ja-JP`).
- Subtitle: Japanese bật mặc định; Vietnamese là tùy chọn.
- AI inference: cloud-first. LLM mặc định dùng cloud API của provider/model lớn, có chất lượng đa ngôn ngữ và tiếng Nhật tốt. Không yêu cầu GPU mạnh hoặc tải model lớn ở cấu hình mặc định.
- STT/TTS: ưu tiên cloud API khi chất lượng, latency, giá và chính sách dữ liệu phù hợp; local provider là tùy chọn thay thế qua adapter.
- Offline: không âm thầm chuyển sang provider trả phí khác. Nếu cloud không khả dụng và local provider chưa được cấu hình, thông báo rõ và giữ text/history local khả dụng.
- AI access strategy: BYOK (`byok_direct`) là mode mặc định hiện tại; kiến trúc trung lập với access mode và chuẩn bị contract cho `managed_gateway`/`local`. Gateway chưa được triển khai và phải qua ADR + business/security review riêng. BYOK key lưu trong OS credential vault; Gateway session credential (nếu có trong tương lai) là secret riêng, không trộn với BYOK key.
- Memory: tự động xử lý nền không cần xác nhận từng mục; người dùng có quyền xem, sửa, xóa, export và tắt/bật.
- Proactive: hỗ trợ hỏi thăm, inactivity trigger và reminders; có global/per-type toggle, quiet hours, cooldown, timezone và daily cap. Mặc định bảo thủ; hành vi chủ động chỉ chạy theo policy đã cấu hình.
- Visual MVP: PNG/GIF/WebP + manifest + CSS effects; Live2D để M6.
- Memory dài hạn và Adaptive Relationship Profile triển khai ở M4 theo automatic background pipeline; Core Personality cố định.
- Proactive scheduler/notifications triển khai ở M5.
- Không lưu audio thô mặc định.

## 15. Quy trình phát triển và GitHub

Chi tiết nằm trong `docs/AGENT_GITHUB_WORKFLOW_v0.5.md`. Các nguyên tắc chuẩn: một task/PR có phạm vi rõ; không code trực tiếp trên `main`; agent làm trên branch/workspace cô lập; coordinator tích hợp; Critic/Challenger/Auditor xác minh độc lập; CI phải chạy; comment phải được xử lý; người dùng quyết định merge rủi ro cao. Với một GitHub identity duy nhất, nhận xét của reviewer agent là advisory và không thay thế required approval độc lập của GitHub. Không sử dụng `--admin` để vượt branch protection.

## 16. Tài liệu tham chiếu kỹ thuật

Các đường dẫn dưới đây dùng để kiểm tra khả năng và điều kiện của ứng viên kỹ thuật; cần xem lại phiên bản, license và yêu cầu phần cứng trước khi triển khai:

- OpenAI Whisper: https://github.com/openai/whisper
- faster-whisper: https://github.com/SYSTRAN/faster-whisper
- Qwen3-TTS: https://github.com/QwenLM/Qwen3-TTS
- Qdrant Python client (local mode): https://github.com/qdrant/qdrant-client
- FastAPI: https://fastapi.tiangolo.com/
- Tauri v2: https://v2.tauri.app/

---

**Kết thúc SRS v0.5.** Mọi thay đổi về hành vi bắt buộc, phạm vi hoặc kiến trúc phải được phản ánh trong tài liệu và/hoặc một ADR trước khi code thay đổi.
