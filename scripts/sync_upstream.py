#!/usr/bin/env python3
"""Synchronize the standalone CTO Advisor skill from alirezarezvani/claude-skills."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
import urllib.parse
import urllib.request

UPSTREAM_OWNER = "alirezarezvani"
UPSTREAM_REPO = "claude-skills"
UPSTREAM_BRANCH = "main"
SKILL_PATH = "c-level-advisor/skills/cto-advisor"
PROTOCOL_PATH = "c-level-advisor/skills/agent-protocol/SKILL.md"
UPSTREAM_REPO_URL = f"https://github.com/{UPSTREAM_OWNER}/{UPSTREAM_REPO}"
UPSTREAM_SKILL_URL = f"{UPSTREAM_REPO_URL}/tree/{UPSTREAM_BRANCH}/{SKILL_PATH}"
ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / ".upstream" / "source.json"
MIRROR_OWNED = {
    "README.md",
    "scripts/sync_upstream.py",
    ".github/workflows/sync-upstream.yml",
    ".upstream/source.json",
}
BROKEN_PROTOCOL_REFERENCE = "../agent-protocol/SKILL.md"
LOCAL_PROTOCOL_REFERENCE = "references/agent-protocol.md"


def run(*args: str, cwd: Path | None = None) -> str:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    completed = subprocess.run(
        args,
        cwd=cwd,
        env=env,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


def github_json(path: str, query: dict[str, str] | None = None):
    url = f"https://api.github.com{path}"
    if query:
        url += "?" + urllib.parse.urlencode(query)
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Marco9442/cto-advisor sync workflow",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def clone_upstream(destination: Path) -> str:
    run(
        "git",
        "clone",
        "--depth=1",
        "--filter=blob:none",
        "--sparse",
        "--branch",
        UPSTREAM_BRANCH,
        UPSTREAM_REPO_URL + ".git",
        str(destination),
    )
    run(
        "git",
        "sparse-checkout",
        "set",
        SKILL_PATH,
        str(PurePosixPath(PROTOCOL_PATH).parent),
        cwd=destination,
    )
    return run("git", "rev-parse", "HEAD", cwd=destination)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def mode_for(path: Path) -> str:
    return "100755" if path.stat().st_mode & stat.S_IXUSR else "100644"


def extract_version(skill_text: str) -> str:
    match = re.search(r"(?m)^\s*version:\s*[\"']?([^\s\"']+)", skill_text)
    if not match:
        raise RuntimeError("SKILL.md metadata.version is missing")
    return match.group(1)


def collect(upstream: Path) -> tuple[list[dict], list[dict], str, str]:
    source_root = upstream / SKILL_PATH
    if not (source_root / "SKILL.md").is_file():
        raise RuntimeError("Upstream CTO Advisor is missing SKILL.md")

    source_records: list[dict] = []
    output_records: list[dict] = []
    for source in sorted(source_root.rglob("*")):
        if source.is_symlink():
            raise RuntimeError(f"Symlink is not allowed in upstream skill: {source}")
        if not source.is_file():
            continue
        relative = PurePosixPath(source.relative_to(source_root).as_posix())
        local_path = relative.as_posix()
        if local_path in MIRROR_OWNED or relative.parts[0] in {".git", ".github", ".upstream"}:
            raise RuntimeError(f"Upstream path conflicts with mirror infrastructure: {local_path}")
        raw = source.read_bytes()
        source_records.append(
            {
                "sourcePath": f"{SKILL_PATH}/{local_path}",
                "sha256": sha256(raw),
                "size": len(raw),
                "mode": mode_for(source),
            }
        )
        output = raw
        transformed = False
        if local_path == "SKILL.md":
            text = raw.decode("utf-8-sig")
            if not text.lstrip().startswith("---"):
                raise RuntimeError("SKILL.md lacks YAML frontmatter")
            occurrences = text.count(BROKEN_PROTOCOL_REFERENCE)
            if occurrences != 1:
                raise RuntimeError(
                    f"Expected one agent-protocol reference, found {occurrences}"
                )
            output = text.replace(BROKEN_PROTOCOL_REFERENCE, LOCAL_PROTOCOL_REFERENCE).encode("utf-8")
            transformed = True
        output_records.append(
            {
                "path": local_path,
                "sourcePath": f"{SKILL_PATH}/{local_path}",
                "sha256": sha256(output),
                "size": len(output),
                "mode": mode_for(source),
                "transformed": transformed,
                "_data": output,
            }
        )

    protocol = upstream / PROTOCOL_PATH
    if not protocol.is_file() or protocol.is_symlink():
        raise RuntimeError("Referenced upstream agent-protocol/SKILL.md is missing")
    protocol_raw = protocol.read_bytes()
    source_records.append(
        {
            "sourcePath": PROTOCOL_PATH,
            "sha256": sha256(protocol_raw),
            "size": len(protocol_raw),
            "mode": mode_for(protocol),
        }
    )
    output_records.append(
        {
            "path": LOCAL_PROTOCOL_REFERENCE,
            "sourcePath": PROTOCOL_PATH,
            "sha256": sha256(protocol_raw),
            "size": len(protocol_raw),
            "mode": "100644",
            "transformed": False,
            "_data": protocol_raw,
        }
    )

    license_file = upstream / "LICENSE"
    if not license_file.is_file() or license_file.is_symlink():
        raise RuntimeError("Upstream LICENSE is missing")
    license_raw = license_file.read_bytes()
    source_records.append(
        {
            "sourcePath": "LICENSE",
            "sha256": sha256(license_raw),
            "size": len(license_raw),
            "mode": mode_for(license_file),
        }
    )
    output_records.append(
        {
            "path": "LICENSE",
            "sourcePath": "LICENSE",
            "sha256": sha256(license_raw),
            "size": len(license_raw),
            "mode": "100644",
            "transformed": False,
            "_data": license_raw,
        }
    )

    skill_text = (source_root / "SKILL.md").read_text(encoding="utf-8-sig")
    version = extract_version(skill_text)
    return source_records, output_records, version, "MIT"


def content_digest(records: list[dict]) -> str:
    digest = hashlib.sha256()
    for record in sorted(records, key=lambda item: item["path"]):
        digest.update(record["path"].encode())
        digest.update(b"\0")
        digest.update(record["mode"].encode())
        digest.update(b"\0")
        digest.update(record["sha256"].encode())
        digest.update(b"\n")
    return digest.hexdigest()


def read_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def remove_previous_files(state: dict) -> None:
    paths = [PurePosixPath(item["path"]) for item in state.get("files", [])]
    for relative in sorted(paths, key=lambda path: len(path.parts), reverse=True):
        if relative.as_posix() in MIRROR_OWNED:
            continue
        target = ROOT / relative.as_posix()
        if target.is_file() or target.is_symlink():
            target.unlink()
    directories = {path.parent for path in paths if path.parent != PurePosixPath(".")}
    for relative in sorted(directories, key=lambda path: len(path.parts), reverse=True):
        target = ROOT / relative.as_posix()
        try:
            target.rmdir()
        except (FileNotFoundError, OSError):
            pass


def write_outputs(records: list[dict]) -> list[dict]:
    clean: list[dict] = []
    for record in records:
        target = ROOT / record["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(record["_data"])
        target.chmod(0o755 if record["mode"] == "100755" else 0o644)
        clean.append({key: value for key, value in record.items() if key != "_data"})
    return clean


def write_readme(version: str, skill_commit: str, skill_commit_date: str) -> None:
    short_commit = skill_commit[:12]
    content = f"""# CTO Advisor

[![Sync upstream](https://github.com/Marco9442/cto-advisor/actions/workflows/sync-upstream.yml/badge.svg)](https://github.com/Marco9442/cto-advisor/actions/workflows/sync-upstream.yml)

这是上游 [`alirezarezvani/claude-skills` 中 `cto-advisor`]({UPSTREAM_SKILL_URL}) 的**自动同步公开镜像**，并整理为可独立安装的标准 Agent Skill GitHub 源。

## 当前版本

- Skill 名称：`cto-advisor`
- 上游版本：`{version}`
- 上游分支：`{UPSTREAM_BRANCH}`
- 最近 Skill 变更：[`{short_commit}`]({UPSTREAM_REPO_URL}/commit/{skill_commit})
- 变更时间：`{skill_commit_date}`
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

原始来源：[`{UPSTREAM_OWNER}/{UPSTREAM_REPO}/{SKILL_PATH}`]({UPSTREAM_SKILL_URL})。

本仓库保留上游 [`LICENSE`](LICENSE)。所有上游内容的权利归原作者和权利人所有。
"""
    (ROOT / "README.md").write_text(content, encoding="utf-8")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="cto-advisor-") as temp:
        upstream = Path(temp) / "upstream"
        source_commit = clone_upstream(upstream)
        source_records, outputs, version, license_id = collect(upstream)
        digest = content_digest(outputs)
        old_state = read_state()
        if old_state.get("contentSha256") == digest:
            print(
                f"CTO Advisor is already current: version {version}, "
                f"commit {old_state.get('skillCommit', source_commit)[:12]}"
            )
            return

        commits = github_json(
            f"/repos/{UPSTREAM_OWNER}/{UPSTREAM_REPO}/commits",
            {"sha": source_commit, "path": SKILL_PATH, "per_page": "1"},
        )
        protocol_commits = github_json(
            f"/repos/{UPSTREAM_OWNER}/{UPSTREAM_REPO}/commits",
            {"sha": source_commit, "path": PROTOCOL_PATH, "per_page": "1"},
        )
        if not commits or not protocol_commits:
            raise RuntimeError("GitHub returned incomplete path commit history")
        skill_commit = commits[0]["sha"]
        skill_commit_date = commits[0]["commit"]["author"]["date"]
        protocol_commit = protocol_commits[0]["sha"]

        remove_previous_files(old_state)
        clean_outputs = write_outputs(outputs)
        write_readme(version, skill_commit, skill_commit_date)
        state = {
            "schemaVersion": 1,
            "upstreamOwner": UPSTREAM_OWNER,
            "upstreamRepository": UPSTREAM_REPO,
            "upstreamBranch": UPSTREAM_BRANCH,
            "upstreamSkillPath": SKILL_PATH,
            "upstreamUrl": UPSTREAM_SKILL_URL,
            "sourceCommit": source_commit,
            "skillCommit": skill_commit,
            "skillCommitDate": skill_commit_date,
            "protocolSourcePath": PROTOCOL_PATH,
            "protocolCommit": protocol_commit,
            "version": version,
            "license": license_id,
            "contentSha256": digest,
            "transformations": [
                {
                    "file": "SKILL.md",
                    "description": (
                        f"Replace {BROKEN_PROTOCOL_REFERENCE} with "
                        f"{LOCAL_PROTOCOL_REFERENCE} so the skill is standalone"
                    ),
                },
                {
                    "file": LOCAL_PROTOCOL_REFERENCE,
                    "description": f"Copy dependency from {PROTOCOL_PATH} without modification",
                },
            ],
            "sourceFiles": sorted(source_records, key=lambda item: item["sourcePath"]),
            "files": sorted(clean_outputs, key=lambda item: item["path"]),
        }
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(
            json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            f"Synced CTO Advisor {version} at {skill_commit[:12]} "
            f"({len(clean_outputs)} mirrored files)"
        )


if __name__ == "__main__":
    main()
