# 可移植的 Cindy 多工作流

这个仓库集中保存可协作迁移的 Cindy 工作流。每条工作流都包含自己的 Skill、脚本、模板和测试；运行态配置、连接器凭证、审计日志、SQLite 数据库和报告只保留在安装目标的 `.cindy/` 中，不进入仓库。

当前包含以下工作流：

- `filo-support-replies`：扫描 Gmail（包括 Spam），检查同事是否已回复、产品能力、Issue/PR 和发布版本，在原线程创建标准 Gmail 富文本回复草稿，并按本地策略决定是否自动发送。
- `filoai-feedback-triage`：扫描 Gmail 与 Feishu，先诊断短反馈，再核对产品、代码、Issue、PR 和发布记录，创建或补充证据充分的 Bug/Feature 工单。
- `cindy-update-poster`：生成 Cindy 日报海报与中英文文案。
- `model-comparison-poster`：从官方模型资料和配置的目录地址核验模型能力/价格，生成中英文对比海报、HTML、PNG 和社媒文案。
- `xiaohongshu-feedback-monitor`：通过用户自己的 Chrome Profile 只读采集小红书评论、私信和群聊，生成增量反馈报告。
- `sausage-man-monitor`：连接现有香肠社区工作台，查询反馈、原文、报表与行动，校验发布一致性并导出；同一个包可供 GitHub 与 Cindy Skills/SkillHub 分发。

## 香肠社区工作台

`node install.mjs --workflow community --target <已有工作目录>` 安装到目标项目的 `.agents/skills/sausage-man-monitor`。需要 Python 3.10+，不创建采集或调度。连接配置放在用户 `~/.config/sausage-man-monitor/config.json`，与 Skill 包独立。

在安装后的 Skill 目录运行：

```bash
python -X utf8 -B scripts/query.py configure --base-url http://WORKBENCH_HOST:8777
python -X utf8 -B scripts/query.py doctor
python -X utf8 -B scripts/query.py search --q 卡顿 --all
```

源码正本为 `skills/sausage-man-monitor`，通过其 `scripts/package_skill.py` 校验、打包、更新与回退。ZIP 可直接在 Cindy「插件 → Skills」导入，也可发布至 SkillHub；两个渠道使用相同文件清单及哈希。安装升级检测本地改动，保留个人连接配置。完整流程见 [安装说明](skills/sausage-man-monitor/references/install.md)。异地客户端仍需可达的工作台地址，本包不建立公网映射。

校验命令：`python -B -m unittest discover -s tests -p test_sausage_skill.py -v`。GitHub Actions 在 Windows 与 Linux 校验并生成可供 Cindy 导入的同一 ZIP。

## Cindy 角色外观资源

`character-bible/` 保存 Cindy 数据人和黑猫宠物的可复用视觉锚点，包括人物/宠物三视图、细节图、独立饰品拆解图、原始参考图和固定提示词。

使用时：

1. 先阅读 [`character-bible/README.md`](character-bible/README.md) 和 [`character-bible/prompts/appearance-lock.md`](character-bible/prompts/appearance-lock.md)。
2. 生成人物时引用人物三视图、人物耳饰拆解图和服装参考图；Cindy 只有解剖学右耳（角色自身的右耳）佩戴约 3 cm 的银色 `>` 耳饰，左耳必须裸露；旧图中的佩戴侧和左右标签不作为依据，以外观锁定提示词为准。
3. 生成猫时引用宠物三视图、猫眼近景和项圈/银牌拆解图；猫是短毛黑猫，虹膜上黑下红渐变、黑色竖瞳，红项圈和带“一”字刻痕的银牌。
4. 角色动作、场景和镜头可以变化，但外观锁定字段不可改。

这套资源只包含静态素材和提示词，不会写入 Gmail、Feishu、GitHub、浏览器凭证或 Scheduler 运行态。

## 一键安装全部工作流

在目标 Cindy 工作目录执行：

```bash
git clone https://github.com/nanaco666/cindy-workflows.git
cd cindy-workflows
node install.mjs --workflow all --target /path/to/cindy-project
```

不传 `--workflow` 时默认也是 `all`。默认是模板模式：只复制 Skill、脚本、配置模板和定时任务模板，不创建或修改线上 Scheduler，不写入 Gmail、Feishu、GitHub 或浏览器凭证。需要在安装过程中交互填写本机配置时，显式加 `--interactive`。

如果只需要一条工作流，可使用以下名称或别名：

```bash
node install.mjs --workflow filo-support-replies --target /path/to/cindy-project
node install.mjs --workflow filoai-feedback-triage --target /path/to/cindy-project
node install.mjs --workflow cindy-update-poster --target /path/to/cindy-project
node install.mjs --workflow model-comparison-poster --target /path/to/cindy-project
node install.mjs --workflow xiaohongshu-feedback-monitor --target /path/to/cindy-project
```

也支持别名：`support`、`triage`、`poster`、`model`、`xiaohongshu`。`--non-interactive` 会保留脱敏占位配置，方便在 CI 或批量安装中先落盘，之后再在本机补齐连接器账号、仓库和水位信息。

安装后：

1. Skill 位于目标目录的 `.agents/skills/`；
2. 回复与开单工作流的本地配置、状态、审计和 SQLite 索引位于 `.cindy/filo-support-automation/`；
3. 海报与小红书工作流的本地目录位于 `.cindy/workflows/<workflow>/`；
4. 使用对应目录里的 `*.txt`（以及小红书的 `*.yaml`）创建独立、默认暂停的 recurring Scheduler 任务；
5. 在 Cindy 中连接该工作流需要的 Gmail、XD Feishu、GitHub 或浏览器连接器后，再运行 preflight 和 Skill 自带检查。

模型对比海报工作流的资源和地址都由安装者配置：`source_urls` 填官方文档/定价页，`catalog_url` 可选，`hero_image`/`asset_dir` 只填当前机器上有授权的资源路径；留空即可生成无外部图片依赖的表格海报。

## 安全与数据边界

公开包内不包含真实账号、OAuth、Token、Cookie、飞书群 ID、Scheduler ID、客户正文、审计 JSONL、SQLite 数据库或本机绝对路径。`.cindy/` 已加入目标项目的 `.gitignore`。公开模板只描述字段和流程，真实身份与运行态数据由安装者在本机配置。

## 校验

```bash
node scripts/check-redaction.mjs
node scripts/check-template-sync.mjs
node scripts/check-package.mjs
python3 /path/to/skill-creator/scripts/quick_validate.py skills/filo-support-replies
python3 /path/to/skill-creator/scripts/quick_validate.py skills/filoai-feedback-triage
python3 /path/to/skill-creator/scripts/quick_validate.py skills/cindy-update-poster
python3 /path/to/skill-creator/scripts/quick_validate.py skills/model-comparison-poster
python3 /path/to/skill-creator/scripts/quick_validate.py skills/xiaohongshu-feedback-monitor
```

各工作流的纯逻辑测试都不需要连接真实服务；请按对应 Skill 目录中的测试说明运行。

## License

MIT；随包品牌和第三方资源仍以其各自授权为准。
