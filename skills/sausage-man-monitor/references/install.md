# 安装、连接与更新

需要 Python 3.10+，无第三方依赖。Windows 使用 `python`，macOS/Linux 若只有 `python3` 则替换命令。本文所有脚本路径相对 Skill 目录。

## 同一份包，两种安装入口

- GitHub：取得固定版本 ZIP，解压后使用 `scripts/package_skill.py install --target 目标Skill目录`；默认先显示预览，确认安装用 `--apply`。`--target` 是最终的 `sausage-man-monitor` 文件夹，不是父目录。
- Cindy：在「插件 → Skills → 导入 Skill」选择同一 ZIP，按需要全局或项目安装。全局导入由 Cindy 管理共享发现路径；插件自带 Skill 与外部 CLI 的发现目录不同，不要假设所有 CLI 都自动能看到。
- SkillHub：在 Cindy 中发布这个完整文件夹。首次选择本人、团队或公开范围；后续版本保留范围。使用宿主实际返回的版本并记录与 GitHub 包内容哈希的对应关系。上传成功不等于审核通过。

通用安装位置为用户 `~/.agents/skills/sausage-man-monitor`（Cindy 共用），或目标 Agent 实际扫描的技能目录（例如 `~/.codex/skills/sausage-man-monitor`）。项目安装放在 `<project>/.agents/skills/sausage-man-monitor`。同一宿主有多个副本时应保持同版本，避免用目录优先级猜测实际加载版本。

## 配置工作台

```sh
python -X utf8 -B scripts/query.py configure --base-url http://WORKBENCH_HOST:8777
python -X utf8 -B scripts/query.py doctor
python -X utf8 -B scripts/query.py summary
```

默认配置在 `~/.config/sausage-man-monitor/config.json`。可使用全局 `--config FILE` 或 `SAUSAGE_WORKBENCH_CONFIG` 选择独立配置，`SAUSAGE_WORKBENCH_URL` 覆盖地址。优先级：命令行 > 环境变量 > 本地配置 > 本机默认。配置与下载文件放在 Skill 目录外，更新不替换它们。

`configure` 只保存配置，不启动工作台；可设置 `--project-root PATH` 供主机工作流使用。跨机地址用工作台主机的实际可达地址；localhost 只指执行命令的电脑。内网/VPN 或已有远程主机执行路径必须可用；本包不自动建立公网映射或变更访问权限。

## 发版与升级

维护者只编辑 Git 仓库的 `skills/sausage-man-monitor` 正本，安装副本通过包更新。

```sh
python -B scripts/package_skill.py seal --version 1.0.0
python -B scripts/package_skill.py verify
python -B scripts/package_skill.py pack --output /path/out/sausage-man-monitor-1.0.0.zip
python -B scripts/package_skill.py install --target /path/skills/sausage-man-monitor
python -B scripts/package_skill.py install --target /path/skills/sausage-man-monitor --apply
```

固定清单只包含 Skill 所需脚本、说明和示例配置；真实地址、运行配置、报表、媒体、数据库、日志与凭据不打包。对外上传前检查 ZIP 清单及内容。

安装器会校验包内文件哈希，预览新增/修改/删除；已安装版本被本地改过时说明冲突并停止，不能静默覆盖。第一次接管无清单旧副本可显式 `--adopt-existing`，仍先预览并完整备份。更新备份位于 Skill 目录旁的 `.sausage-man-monitor-backups/`，带回执，保留配置和非包文件。

回退命令：`scripts/package_skill.py rollback --target PATH --backup BACKUP_DIRECTORY`，预览后加 `--apply`。只恢复对应 Skill 文件；不会回退服务器业务数据。修改过的已安装内容需先处理冲突，不能无声丢弃。

工作台数据更新不要求重新安装 Skill，下次查询读取新发布。只有能力/接口/使用规则发生变化才发布新版包。
