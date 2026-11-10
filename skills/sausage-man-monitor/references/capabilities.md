# 查询能力与数据口径

所有 HTTP 命令只 GET；不会创建维护会话或执行业务写入。脚本成功输出 JSON，失败返回非零状态及错误分类。下载与配置写入发生在明确指定的本机文件中。

| 命令 | 接口与用途 |
| --- | --- |
| `doctor` | 校验安装包、Python、snapshot / batches / workflow state 的可用性与契约；不启动工作台 |
| `summary` | snapshot + batches 同快照校验；返回发布、窗口、已知限制、索引来源数 |
| `snapshot` | `/api/snapshot`，议题、热点、队列与审核视图；不是逐源 canonical 表 |
| `batches` | `/api/workflow/feedback/batches`，批次 ID、snapshot、current、limits |
| `search --q 卡顿 --all` | `/api/workflow/feedback/search`，完整分页；显式历史批次用 `--batch ID` |
| `originals --ids ID --snapshot SHA` | `/api/workflow/feedback/originals`，核对来源 ID 集合和快照；仅当前发布 |
| `state` / `reports` | `/api/workflow/state`；reports 只列已发布报表和实际下载链接 |
| `report --id ID` | `/api/workflow/report/{id}`，`project.report.v1` |
| `inputs --id metrics` | metrics/content/activities/schedule/analysis/article_daily/reading_sources/article_history |
| `coverage --month YYYY-MM` | `/api/workflow/source-status`，平台日期覆盖 |
| `todos` / `action --id ID` | `/api/todos`、`/api/workflow/actions/{id}`，实际行动 ID、进展和依据 |
| `review` | `/api/topic-review`，当前审核与规则状态 |
| `history --kind KIND --before N` | `/api/workflow/review-history`，根据服务返回的游标继续读取 |
| `action-links --platform NAME --activity ID` | `/api/workflow/action-links` |
| `backups` | `/api/workflow/review-backups`，备份目录；此客户端不恢复业务数据库 |
| `manifest` / `export --output FILE` | `/api/export/manifest` + `/api/export`；校验原始字节 SHA 后导出 |
| `download --url URL --output FILE` | 已有 `/media/`、`/reports/download/` 地址；不把服务器文件路径拼成下载接口 |

查询的通用选项：`--base-url URL`、`--config FILE`、`--timeout SECONDS`、`--links`，均位于子命令前。`--links` 在不改原始数据的情况下，附加绝对链接与不可远程访问的主机路径列表。

检索支持 `--kind review|topic`、`--topic ID`、`--start YYYY-MM-DD`、`--end YYYY-MM-DD`、`--scope feedback|all`、`--page N`、`--all`、`--max-pages N`。默认仅反馈索引，`--all` 与非零 `--page` 不同时使用；达到页数上限返回明确错误，不把截断结果说成完整。批次在读取前后都检查，读取期间当前发布变化时停止并提示重新查询，不无限重试。

起止日期均包含当天，筛选的是来源发表日；评论发生日可能不同。报表 `window.end_exclusive` 则不包含当天。原文一次最多 20 个不同且非空的来源 ID。

反馈索引 `feedback_count` 和默认搜索只可能覆盖被议题引用的来源，不能替代 canonical 的反馈分母。即使 `--scope all` 查到全部来源，也需要对应发布的归档依据才能判断哪些是反馈。未归入议题、未知情绪与证据不足如实保留。

媒体链接从原文/快照中实际读取。图片、视频、音轨需要相应的真实审看能力；inventory-only 不代表已读。返回的本机路径只是发布证据定位信息，远程下载使用服务器已经暴露的 URL。

HTTP 403 表示访问被服务拒绝；404 表示接口、版本或文件不存在；409 表示发布/数据冲突；503 表示存储或绑定暂不可用。连接错误与这些 HTTP 错误分开输出。接口错误不能通过关闭校验、扩大监听或删除锁规避。
