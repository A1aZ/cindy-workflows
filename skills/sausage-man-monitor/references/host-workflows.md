# 主机端工作流（仅在用户要求业务操作时读取）

查询不依赖项目根；本节操作要求真实的项目 checkout 和已有授权。项目根由本地配置 `project_root` 或当前任务指定，不硬编码用户名。可以用 `doctor --host` 检查必要文件是否齐全；它不运行采集或发布。

开始时读取该项目的 `AGENTS.md`、根 `HANDOFF.md` 最新交付、`workflow/PITFALLS.md` 与 `workflow/AGENT-HANDOFF.md`。实际服务、最新冻结交付优先于历史 runbook。核对并发任务、人工账本、规则 pin；不要停止不明进程、删锁或重复提交结果未知的任务。

| 目标 | 现有入口 | 按需读取 |
| --- | --- | --- |
| 生成/续跑运营报表 | `scripts/project-workflow.ps1 -Mode Doctor`、`-Mode Status` 后按实际任务 Start/Resume | `workflow/README.md`、`workflow/REPORT-CONTRACT.md` |
| 导入指标、内容、活动、排期 | `-Mode Import`，携带实际 expected revision | 同上；真实输入与冻结版本 |
| 原生分析 | NativePending / AcceptNative，真实宿主与输入输出回执 | `workflow/CINDY-REPORT-ANALYSIS.md` |
| 接入舆情冻结结果 | RegisterSentiment，核对 REPORT-BRIDGE 与哈希 | `workflow/CINDY-HANDOFF.md` |
| Tap Insights / TapTap 公开舆情采集 | 沿用 Cindy 现有 XDS；先看任务回执 | `workflow/CINDY-HANDOFF.md`、`workflow/TAPTAP-AUTOMATION.md` |
| 审核、修正、行动、备份恢复 | 工作台现有 UI 或真实 POST 契约，保留 revision、会话、CSRF | `project_workflow/web.py`、`project_workflow/actions.py`、`operations-ui/server.py` 与审核模块 |
| 装配与发布 | 独立新版本；实际浏览器验收与明确回滚方式 | `workflow/RELEASE-CHAIN.md` |

最终运营报表为 `project.report.v1`。动态计算北京时间窗口，查询当前已存在的同窗任务，不重复 Start。窗口不足、无同口径前期、缺数保持真实；缺值使用 null。

新采集、生成、修订使用独立版本目录，不覆盖旧冻结、失败回执、benchmark、人工审核账本或修正历史。语义与多模态判断来自真实 Agent 阅读和实际证据，程序只处理确定性校验。引文逐字复制。

审核库只追加；本批次修正不自动发布未来规则。未来规则启用按用户明确授权，新批次固定版本，历史不自动重算。工作流与反馈审核会话不同，不互换 CSRF；LAN 权限遵循实际服务配置。

TapTap 运营后台和 QQ 群获取需检查实际接入状态，不能将公开舆情采集当成后台接入。公众号后续由 Cindy 执行；不要凭历史记录恢复已暂停的 Codex 自动化或创建重复调度。

飞书相关功能优先官方 `lark-cli`，用 `--help` 核对本机版本，再检查配置和授权。用户授权过期时由 CLI 发起并让用户本人确认，不读取客户端凭据或改用机器人冒充用户。写操作以当前任务的实际授权为准。

发布要核对 snapshot、UI、workflow assets 同源，候选浏览器验收通过才标记 deployable。`release_chain.py` 会重启服务，不能当只读诊断。保留现有 8777 入口和独立旧服务；Skill 安装升级不调整运行中的服务与定时任务。
