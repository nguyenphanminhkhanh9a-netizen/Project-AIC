# PROJECT AIC — AUTONOMOUS MULTI-AGENT GITHUB WORKFLOW

**Phiên bản:** 0.5  
**Ngày:** 04/11/2026  
**Mục đích:** Quy định cách Antigravity Teamwork, Git và GitHub phối hợp để thay đổi source code có thể review, kiểm thử, truy vết và rollback.

## 1. Mục tiêu và ranh giới

Quy trình này biến việc vibe-coding thành một luồng phát triển có kiểm soát. Antigravity Teamwork phân công và xác minh công việc; Git quản lý lịch sử local; GitHub lưu branch/commit/PR/CI và các quyết định review.

Các công cụ không thay thế lẫn nhau:

- **Antigravity `/teamwork`:** chia task, điều phối Explorer/Worker/Critic/Challenger/Auditor/Success Auditor và giữ handoff.
- **Git:** tạo checkpoint, branch và lịch sử thay đổi.
- **GitHub CLI (`gh`):** thao tác GitHub bằng quyền của tài khoản đang xác thực: Issue, PR, comment, review, checks, merge.
- **GitHub Actions/CI:** chạy kiểm tra tự động trên PR.
- **Project Owner:** duyệt scope, thay đổi rủi ro cao, branch rules, secrets, quyền truy cập và release.

`gh` không có “toàn quyền” mặc định. Mọi thao tác bị giới hạn bởi quyền tài khoản/token đang active. Không bao giờ coi việc đã cài `gh` là đồng nghĩa với đã đăng nhập hoặc đã có quyền write/admin.

## 2. Phân vai Teamwork

| Vai trò | Nhiệm vụ | Ranh giới |
|---|---|---|
| Project Owner | Giao mục tiêu, duyệt plan, quyết định rủi ro cao và merge/release | Không cần review từng dòng code; giữ quyền quyết định cuối cùng |
| Sentinel/Coordinator | Nhận brief đã duyệt, tạo milestone plan, điều phối, handoff và tổng kết | Không để worker tự mở rộng scope |
| Project Orchestrator | Chia task, dependency, file ownership, tổng hợp đầu ra | Một người/agent chịu trách nhiệm tích hợp |
| Explorer | Khảo sát repo/call graph/dependencies ở chế độ read-only | Không sửa source trong pha khảo sát |
| Worker/Implementer | Code, test, commit và push branch được giao | Ownership theo file/thư mục; không chạm file của worker khác |
| Critic/Reviewer | Review diff độc lập, correctness, interface, security, maintainability | Review không đồng nghĩa với GitHub approval |
| Challenger | Viết test đối kháng, edge case, failure path | Không sửa implementation đang được review trừ khi được giao riêng |
| Auditor | Xác minh lệnh test và output thật, phát hiện test giả/skipped | Không kết luận pass khi không có bằng chứng |
| Success Auditor | End-to-end verification trước khi bàn giao milestone | Báo rõ phần chưa được xác minh |

Nếu Teamwork runtime không cung cấp chính xác một vai trò, Coordinator phải ghi rõ và mô phỏng bằng agent/task độc lập hoặc tuần tự hóa. Không bịa rằng subagent đã chạy.

## 3. Quy tắc cô lập agent và Git workspace

1. Trước khi sửa file, ghi nhận `git status --short`, branch, HEAD và diff. Không reset, clean, checkout đè hoặc stash thay đổi có sẵn của người dùng nếu chưa được cho phép.
2. Dùng workspace cô lập của Teamwork. Phân công ownership không chồng lấn. Không để hai worker cùng ghi vào một file hoặc cùng điều khiển một working tree/branch đồng thời.
3. Coordinator sở hữu integration branch và là người tích hợp các patch/worktree output. Mỗi task độc lập có branch hoặc worktree riêng nếu cách tổ chức repo hỗ trợ.
4. Không dùng branch `main` để phát triển. Không push trực tiếp vào `main`, không force-push, không rewrite lịch sử đã chia sẻ.
5. Nếu phát hiện uncommitted changes không thuộc task, dừng và báo owner; không tự ý loại bỏ.

## 4. GitHub CLI preflight

Chạy các lệnh kiểm tra không tiết lộ token:

```powershell
gh --version
git --version
gh auth status
git status --short
git branch --show-current
git remote -v
gh repo view
```

Nếu `gh auth status` báo chưa đăng nhập, owner thực hiện tương tác:

```powershell
gh auth login
```

Sau đó kiểm tra lại `gh auth status`. Không chạy `gh auth status --show-token`, `gh auth token`, không echo `GH_TOKEN`/`GITHUB_TOKEN`, không paste token vào Antigravity prompt, Issue, PR, terminal transcript hoặc log. GitHub CLI mặc định dùng OS credential store khi có; môi trường thiếu credential store có thể có fallback plaintext tùy cấu hình, vì vậy không yêu cầu agent trích xuất token hoặc tự thay đổi cách lưu credential.

Trước khi mở PR, xác nhận remote đúng owner/repository và branch target đúng. Nếu repo không có remote hoặc `gh repo view` không xác định được repo, dừng và hỏi owner; không tự tạo public repository.

## 5. Branch, Issue, commit và Pull Request

### 5.1. Naming

Dùng tên ngắn, mô tả rõ:

- `feature/issue-<id>-<slug>`
- `fix/issue-<id>-<slug>`
- `docs/issue-<id>-<slug>`
- `refactor/issue-<id>-<slug>`

Nếu chưa có GitHub Issue, Coordinator có thể dùng task ID ngắn trong branch name; không cần tự động tạo Issue public nếu owner chưa yêu cầu.

### 5.2. Trước commit

- Kiểm tra `git diff` và `git status`.
- Chạy test phù hợp; ghi rõ command, pass/fail/skipped.
- Kiểm tra secret, `.env`, SQLite/runtime data, raw audio, model weights, personal data và build artifacts không bị stage.
- Commit nhỏ, message nêu hành động và scope.
- Không gộp các thay đổi ngoài task vào PR.

### 5.3. PR body bắt buộc

Mỗi PR phải mô tả:

1. Mục tiêu/Issue liên quan.
2. Scope và các thay đổi chính.
3. Files/modules bị ảnh hưởng.
4. Architecture/API/DB changes và migration/compatibility notes.
5. Tests đã chạy với kết quả thật.
6. Screenshots/video nếu thay đổi UI có ý nghĩa.
7. Risk level: low / medium / high.
8. Known limitations, rollback plan và các mục chưa kiểm thử.

PR nên ở trạng thái Draft khi chưa sẵn sàng review. Chỉ chuyển Ready khi worker đã hoàn tất self-check.

## 6. Review loop — Worker → Critic → Worker

1. Worker tạo PR và cung cấp diff/branch/commit SHA cho Coordinator.
2. Critic đọc diff độc lập; không chỉ đọc mô tả của Worker. Kiểm tra correctness, regressions, edge cases, security, data privacy, architectural boundaries và test coverage.
3. Challenger bổ sung test cho failure paths/edge cases có rủi ro.
4. Reviewer ghi nhận findings có severity, file/line reference, lý do và cách tái hiện. Không đưa nhận xét mơ hồ kiểu “code chưa tốt”.
5. Worker trả lời từng finding, sửa code hoặc giải thích có bằng chứng vì sao không áp dụng. Finding chưa xử lý phải được đánh dấu unresolved và chuyển Owner khi cần.
6. Mọi commit sửa sau review phải chạy lại test phù hợp. Nếu branch protection bật dismiss stale approvals, lần push mới có thể cần review lại.
7. Auditor xác minh command/output thực tế; Success Auditor chạy smoke/E2E checklist phù hợp với milestone.
8. Coordinator xác nhận CI và conversations trước khi đề xuất merge.

*Lưu ý bắt buộc:* Toàn bộ quy trình 9 bước, 13 nguyên tắc kỹ thuật cốt lõi và hệ thống 6 trạng thái Review Gate được quy định bắt buộc vĩnh viễn tại `CODE_REVIEW_POLICY.md`. Tuyệt đối không sử dụng `READY FOR OWNER REVIEW` khi Review Gate chưa đạt `REVIEW_APPROVED`.

## 7. Một GitHub identity không tạo ra reviewer identity thứ hai

Đây là quy tắc quan trọng:

- Nếu tất cả agent dùng chung `gh auth` của owner, GitHub nhìn thấy các hành động dưới cùng một GitHub account.
- Comment/review notes do AI tạo vẫn hữu ích cho quá trình kiểm tra, nhưng không được giả nhận là một approval độc lập hợp lệ.
- GitHub không cho PR author approve chính PR của mình. Vì thế, nếu agent tạo PR bằng identity của owner, chính account đó không thể approve PR như một người khác.
- Nếu sau này muốn required approval từ bot reviewer, phải thiết lập một GitHub App/service identity riêng, giới hạn quyền tối thiểu và review kỹ cách cấp/thu hồi token. Không tạo tài khoản giả hoặc chia sẻ token thô giữa agents.
- Trong giai đoạn đầu, AI review là advisory; owner tự review diff/CI và thực hiện merge thủ công. Required approvals chỉ bật khi repo có reviewer identity độc lập có quyền phù hợp.

## 8. Merge policy và phân loại rủi ro

| Mức | Ví dụ | Quy tắc merge |
|---|---|---|
| Low | README/docs, comment, test không đổi behavior, UI polish nhỏ | Sau khi có review độc lập, CI pass, conversations resolved; có thể xem xét auto-merge về sau |
| Medium | Feature UI, provider adapter, refactor module, API contract không breaking | Owner review PR summary/diff chính; merge thủ công trong giai đoạn đầu |
| High | API key/credential store, auth, Tauri permissions, DB migration, memory delete/export, privacy, provider routing/billing, GitHub Actions/branch rules, dependencies lớn, installer/release | Owner approval bắt buộc; merge thủ công; có test/security plan và rollback note |

M0 rollout mặc định: **mọi PR merge thủ công bởi owner**. Sau 3–5 PR thành công, có thể thí điểm `gh pr merge --auto --squash` cho PR low-risk khi mọi required checks/rules đã cấu hình và owner chủ động cho phép.

Tuyệt đối không dùng `gh pr merge --admin`, không tắt required checks, không dismiss blocking review một cách máy móc và không force-push để vượt quy tắc.

## 9. Branch protection khuyến nghị cho `main`

Thiết lập tại GitHub repository → Settings → Rules → Rulesets (hoặc Branches / Branch protection rule):

- Target branch: `main`.
- Require a pull request before merging.
- Require relevant status checks (sau khi biết chính xác tên job CI).
- Require conversation resolution before merging.
- Block force pushes.
- Block branch deletion.
- Dismiss stale approvals / require approval of most recent reviewable push nếu có independent approval workflow.
- Không allow bypassing protections; không cấp quyền admin cho agent.

**Lưu ý:** nếu repository chỉ có một GitHub identity và owner là PR author, đừng bật required approval một cách khiến không ai có thể approve PR. Có thể bắt đầu với PR + CI + conversation resolution + owner manual review; thêm required approval khi có collaborator/bot identity độc lập hợp lệ.

## 10. GitHub Actions / CI tối thiểu

M0 cần CI không phụ thuộc API key thật:

- Frontend install, typecheck, lint và build.
- Backend install theo lockfile và pytest.
- Static checks/format check phù hợp.
- Không yêu cầu LLM/STT/TTS cloud key trong CI; dùng mock provider.
- Không in secrets; workflow không cần secrets phải không xin quyền secret.
- Permissions của workflow theo nguyên tắc least privilege; chỉ cấp `contents: read` cho CI kiểm tra thông thường, mở quyền viết chỉ khi cần một job cụ thể và có phê duyệt.

Agent không tự thêm secret, thay repository Actions permissions hoặc đổi branch protection nếu chưa được owner giao rõ.


## 10.1. Quy tắc thay đổi AI access strategy (BYOK / Gateway / Local)

- Baseline hiện tại là `byok_direct`; M0 chỉ tạo abstraction/contract/mock, M1 mới triển khai BYOK thật.
- Không hard-code BYOK trong Conversation Orchestrator, prompt composer hoặc UI chat flow. Route phải đi qua `AIAccessRouter`/`AccessStrategyRegistry`.
- Tách `ProviderAdapter` (API/model protocol) khỏi `AIAccessStrategy` (access path/auth boundary). Không đưa raw key vào task description, logs, PR, issue hoặc test fixture.
- Bật `managed_gateway` là thay đổi kiến trúc và sản phẩm mức high-risk. Bắt buộc Owner duyệt ADR, threat model, account/auth, tenant isolation, billing/usage metering, quota, abuse protection, privacy/retention và vận hành server trước khi code.
- Gateway account/session token không phải BYOK provider key; phải có storage namespace, expiry, rotation, revocation và deletion policy riêng. Gateway tuyệt đối không nhận BYOK key.
- Không cho phép mode tự fallback. Per-capability route (LLM/STT/TTS/embeddings) phải hiển thị rõ mode, provider/model, data destination và bên chịu billing.
- Không triển khai Gateway service/client thật trong M0/M1. Nếu task có nguy cơ chạm các ranh giới trên, dừng và yêu cầu Owner phê duyệt scope riêng.

## 11. Lệnh `gh` thường dùng

```powershell
# Xem trạng thái xác thực (không hiển thị token)
gh auth status

# Xem repo hiện tại
gh repo view

# Tạo PR từ branch hiện tại (sau khi push)
gh pr create --draft --fill

# Xem PR và diff
gh pr view <PR_NUMBER>
gh pr diff <PR_NUMBER>

# Xem checks
gh pr checks <PR_NUMBER>

# Gửi comment tổng hợp (AI review advisory nếu cùng identity)
gh pr comment <PR_NUMBER> --body "Review summary: ..."

# Yêu cầu auto-merge chỉ khi Owner cho phép và mọi rule/check đã thỏa
# gh pr merge <PR_NUMBER> --auto --squash
```

Không chạy lệnh tạo/merge PR nếu chưa xác nhận đúng repository, base branch, head branch và quyền thực hiện. Không dùng `--admin`.

## 12. Milestone handoff template

```markdown
## Milestone Report
- Task / Issue:
- Branch / PR:
- Base SHA / Head SHA:
- Files changed:
- Architecture/API/DB impact:
- Review findings and resolution:
- Commands executed:
- Test results (pass/fail/skipped):
- CI status:
- Security/privacy checks:
- Known limitations:
- Risk level:
- Merge recommendation:
- Owner decisions required:
```

## 13. Stop conditions — phải dừng và báo owner

- Working tree có thay đổi không thuộc task hoặc không rõ chủ sở hữu.
- Remote/repository/base branch không đúng hoặc không xác định.
- Có secret/credential/audio/memory riêng tư bị stage hoặc xuất hiện trong diff.
- Muốn sửa branch protection, repository permission, GitHub Actions secrets hoặc quyền token.
- Có migration phá hủy dữ liệu, thay đổi authentication/security/privacy hoặc provider billing/routing.
- Test bắt buộc fail, chưa chạy, hoặc chỉ pass nhờ mock sai phạm vi.
- Review finding severity high chưa được xử lý.
- Xung đột kiến trúc giữa SRS/Architecture và code hiện tại.
- Cần bypass branch protection, force push, delete branch quan trọng hoặc dùng admin privileges.

## 14. Tài liệu tham chiếu chính thức

- Antigravity Teamwork: https://antigravity.google/docs/teamwork/
- GitHub protected branches: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
- GitHub CLI PR commands: https://cli.github.com/manual/gh_pr
- GitHub CLI merge command/options: https://cli.github.com/manual/gh_help_reference
- GitHub CLI authentication: https://cli.github.com/manual/gh_auth_login
- GitHub rule: pull request author cannot approve own PR: https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/approving-a-pull-request-with-required-reviews
- Windows credential handling: https://learn.microsoft.com/en-us/windows/win32/secbp/handling-passwords
- Project AIC Permanent Code Review Policy: `CODE_REVIEW_POLICY.md` (root repository)

---

**Nguyên tắc cuối:** agent có thể tự triển khai và tự kiểm thử phần việc được giao; không được tự trao cho mình quyền vượt rào. Code đi qua branch/PR/CI; `main` chỉ nhận thay đổi đã đủ bằng chứng và đúng mức phê duyệt.
