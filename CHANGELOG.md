# CHANGELOG

版本格式：`vMAJOR.MINOR.PATCH`
- MAJOR：架构或角色定义的重大变更
- MINOR：新功能、新评分维度、新提示词结构
- PATCH：bug 修复、文档更新

---

## [v0.3.0] — 2026-03-14 · 使命守门重构

### 新增
- **briefing.md**：顶部加入「⚠️ 项目根本使命」强制锚点（在火星种出西红柿）
- **briefing.md**：农夫输出格式增加「火星种植实现路径」章节
- **歌者评分**：新增第6维度「使命一致性」（20分），总分由5×20=100改为6×20=120折算100
- **歌者提示词**：加入使命守门规则，纯数据/金融方案强制 not_passed
- **farmer.py**：system_prompt 注入项目根本使命
- **farmer.py**：`think` 参数改为读取 `FARMER_THINK` 环境变量，不再硬编码
- **singer.py**：折算逻辑强制执行（无论歌者是否自行计算 total）
- **epoch-answers.md**：纪元1答案加农场主偏航警告注释
- **CHANGELOG.md**：本文件，引入版本管理
- **src/prompts/farmer.md**：更新为参考文档，标注实际加载路径

### 修复
- `farmer.py` think 参数硬编码 False，不读环境变量（🔴 P0）
- `farmer.py` system_prompt 无使命约束（🔴 P0）
- `singer.py` 折算逻辑只在特定条件触发（🔴 P0）
- `epoch.json` 停留在未授权的纪元2状态（🔴 P0，已重置）
- `epoch-answers.md` 偏航答案无警告（🔴 P0）
- `src/prompts/farmer.md` 是死文件（🟡 P1，已更新说明）
- DESIGN.md / README.md 使命描述缺失（🟡 P1）

### 已知问题（待后续版本）
- 歌者 `next_focus` 指向仍依赖 LLM 自觉，无强制机制
- 纪元1已知定律中的偏航内容（数据资产化方向）仍会传给后续文明，需要农场主审阅清理

---

## [v0.2.0] — 2026-03-14 · 详细日志与史书模型信息

### 新增
- **run.py**：VERBOSE 模式，`↳` 前缀的详细日志
- **farmer.md / singer.md**：顶部运行元数据表格（模型名、think开关、时间戳）
- **run.py**：Loop 启动时打印角色配置摘要
- **.env**：新增 `FARMER_THINK`、`VERBOSE` 变量

---

## [v0.1.1] — 2026-03-14 · 模型调用修复

### 修复
- **根本原因**：OpenAI compat 接口（`/v1/chat/completions`）不支持 `think` 参数
- **修复**：改用 Ollama 原生 `/api/chat` 接口，`think: false/true` 参数正常生效
- **农夫模型**：从 `qwen3.5:0.8b` 升级至 `qwen3.5:2b`（更高质量输出）
- **DESIGN.md**：删除过时的 suanji 备用节点说明

---

## [v0.1.0] — 2026-03-13 · 三角色架构确立

### 新增
- 三角色架构：农场主（灵耳/Claude Sonnet）+ 农夫（Ollama）+ 歌者（DeepSeek）
- Controller 主循环（run.py）
- briefing.md 动态生成（含命题/验收标准/已知定律/歌者提示）
- git commit 自动化：每文明一条，格式 `e{N}-civ-{NNN} | 死亡 | 时长 | 模型 | tokens | 得分 | 墓志铭`
- epoch.md 文明进度表（含模型、时长、token、死亡、得分列）
- discoveries.md 已知定律积累
- epoch-answers.md 跨纪元答案传承

### 修复（相较草稿）
- 删除「情报员」第四角色（草稿遗留）
- 修复农夫 context 为空（briefing.md 直接作为输入）
- 修复歌者叙事主角错误（改为描述农夫）
- 修复 singer.md 占位符转义问题（`{farmer_model}` 等）

---

## 版本状态

| 版本 | 状态 | 纪元覆盖 |
|---|---|---|
| v0.1.0 | ✅ 已发布 | 纪元1 #001-#016 |
| v0.1.1 | ✅ 已发布 | 纪元1 #031-#056 |
| v0.2.0 | ✅ 已发布 | 纪元1 #043-#056 |
| v0.3.0 | ✅ 已发布 | 纪元2起 |
