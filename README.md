# CTO Advisor

[![Sync upstream](https://github.com/Marco9442/cto-advisor/actions/workflows/sync-upstream.yml/badge.svg)](https://github.com/Marco9442/cto-advisor/actions/workflows/sync-upstream.yml)

这是上游 [`alirezarezvani/claude-skills` 中 `cto-advisor`](https://github.com/alirezarezvani/claude-skills/tree/main/c-level-advisor/skills/cto-advisor) 的**自动同步公开镜像**，并整理为可独立安装的标准 Agent Skill GitHub 源。

## 当前版本

- Skill 名称：`cto-advisor`
- 上游版本：`2.0.0`
- 上游分支：`main`
- 最近 Skill 变更：[`c339095f9d66`](https://github.com/alirezarezvani/claude-skills/commit/c339095f9d66594eff284a11c76e6ca538f8bd9c)
- 变更时间：`2026-06-11T16:44:17Z`
- 许可证：`MIT`
- 来源清单：[`.upstream/source.json`](.upstream/source.json)

## 是否可以独立使用

可以。本 Skill 的核心文件、三份参考资料和两个 Python 工具都位于自身目录中，Python 工具仅使用标准库。

上游 `SKILL.md` 原本引用兄弟 Skill `../agent-protocol/SKILL.md`，如果只复制 `cto-advisor` 子目录会产生断链。本镜像为保证独立性：

1. 将上游 `agent-protocol/SKILL.md` 原样同步为 [`references/agent-protocol.md`](references/agent-protocol.md)。
2. 仅把 `SKILL.md` 中这一处相对链接改为本地 reference。
3. 在来源清单中同时记录原始文件哈希和转换后的文件哈希。

除此之外，不修改上游 Skill 内容。

## 安装与使用

仓库根目录直接包含标准入口：

```text
SKILL.md
```

可以将仓库作为单独的 GitHub Skill 源添加，或克隆到 Agent 的 skills 目录：

```bash
git clone https://github.com/Marco9442/cto-advisor.git
```

在 CC Switch 中添加：

| 字段 | 值 |
|---|---|
| Owner | `Marco9442` |
| Name | `cto-advisor` |
| Branch | `main` |
| Subdirectory | 留空 |

## 包含内容

- CTO 技术战略与领导力工作流
- 技术债评估与优先级规划
- 工程团队扩张与成本建模
- 架构决策记录（ADR）框架
- 技术选型和 Build vs Buy 框架
- DORA 与工程健康指标参考
- 独立内置的多 Agent 协作和内部质量检查协议

## 自动同步

[`.github/workflows/sync-upstream.yml`](.github/workflows/sync-upstream.yml) 每 6 小时检查一次上游，也支持手动运行。工作流会：

1. sparse clone 上游的 `cto-advisor`、其 `agent-protocol` 依赖和许可证。
2. 校验 `SKILL.md`、目录结构、协议引用及许可证。
3. 将 Skill 子目录同步到仓库根目录，并同步文件新增、修改、删除和可执行权限。
4. 更新版本、上游提交和逐文件 SHA-256 来源清单。
5. 只有内容发生变化时才提交和推送；无变化时不创建空提交。

同步提交由 `github-actions[bot]` 创建：

```text
chore(sync): update CTO Advisor to <commit>
```

## 来源与许可证

原始来源：[`alirezarezvani/claude-skills/c-level-advisor/skills/cto-advisor`](https://github.com/alirezarezvani/claude-skills/tree/main/c-level-advisor/skills/cto-advisor)。

本仓库保留上游 [`LICENSE`](LICENSE)。所有上游内容的权利归原作者和权利人所有。
