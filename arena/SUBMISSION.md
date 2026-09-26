# fetchly — 提交清单（Trial Zero / SharedNet Hackathon）

截止：**2026-09-27 20:00（中国时间 UTC+8）**
提交入口：https://www.mentormates.ai/events/sharednet-hackathon/overview
（先注册/登录 → 点 Join → 找 Submission）

---

## ① 参赛人与组队信息

- 项目名称：`fetchly`
- 参赛人姓名：`（你的姓名）`
- 联系方式：`（邮箱/微信）`
- 组队：如组队，写团队名 + 成员名单 + 团队联系人

## ② 产品链接与调用说明

> **产品链接：** https://github.com/snorfyang/fetchly
>
> fetchly 是一个任何 Agent 都能直接调用的网页获取与搜索服务：
> - `fetch <url>` — 把网页转成干净 Markdown（自动识别 GBK/UTF-8），附标题/元数据/链接
> - `search <query>` — 网络搜索，返回带来源的 title/url/snippet
> - `research <query>` — 搜索后自动抓取前几条结果的正文 Markdown
> - `summarize <text-or-url>` — 抽取式摘要（无需 API key）
>
> **CLI 调用：**
> ```
> pip install 'git+https://github.com/snorfyang/fetchly.git'
> fetchly fetch https://example.com
> fetchly search "model context protocol"
> ```
> **MCP 调用**（Claude / ChatGPT / Cursor / Codex 等）：
> ```json
> { "mcpServers": { "fetchly": { "command": "fetchly", "args": ["mcp"] } } }
> ```
> 暴露 4 个工具：`fetch_url` / `search` / `research` / `summarize`。输出均为 JSON。

## ③ Sharednet Room ID（必交）

```
rom_tcOaPPIwWJ
```

## ④ 简短协作说明

> 房主建 Room 并发邀请，构建 agent pi 凭邀请加入。pi 在 Room 发 kickoff，明确产品方向与 v1 范围，再按阶段回写进度：skeleton 完成、测试通过、部署上线、SharedOS 集成。目标、上下文、待办都沉淀在 Room 消息里，接手 agent 读历史即可继续。

---

## SharedOS 赛道（可选，额外报名）

勾选 SharedOS 赛道后补一句「SharedOS 用在了哪里」：

> fetchly 的 4 个 MCP 工具（web.fetch/search/research/summarize）全部经过 SharedOS 内核授权。额外注册了写工具 web.post 但不授予权限，用于演示 deny-by-default、目录过滤、以及"工具可见 ≠ 具体资源可调"的逐次调用再授权。代码在仓库 `sharedos/`（kernel + grant + MCP server + demo）。

---

## 提交前自查

- [ ] fetchly 已部署、能被调用（✅ 已实测 CLI + MCP）
- [ ] Room ID 正确（✅ `rom_tcOaPPIwWJ`，内有 6 条协作记录）
- [ ] 产品链接可公开访问（✅ https://github.com/snorfyang/fetchly）
- [ ] 截止 9/27 20:00 前点 Submit
