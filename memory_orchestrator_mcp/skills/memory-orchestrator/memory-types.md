# Memory Types — Detailed Routing Criteria

Detailed judgement rules for the four memory types. The quick table in `SKILL.md`
covers ~90% of cases; consult this file only for borderline classification.

## user — 判断标准

`user` 记录**用户本人的持久特征**，用于个性化协作。存入 token 绑定的当前 project，无需指定 project_id（传入也会被忽略）。

触发条件（满足任一即保存为 user）：
- 用户的角色/职位（前端工程师、数据科学家、独立开发者）
- 技术深度：某语言/框架的熟练程度（精通 Go、初次接触 React）
- 沟通偏好：详细说明 vs 简洁回复、中文 vs 英文
- 工作习惯：偏好 TDD、不喜欢 mock、prefer small PRs
- 知识边界：有哪些领域需要更多解释 vs 可以直接跳过基础

**不**属于 user：
- 项目决策、技术选型（归入 project）
- AI 被纠正的行为（归入 feedback）
- 临时工作状态或当前任务进展

**user 写法：**
```
[用户特征描述]
How to apply: 影响所有未来对话的回复方式
```

---

## feedback — 判断标准

`feedback` 专门记录**对 AI 行为的纠正**和**已验证的做法**，不记录项目事实。

触发条件（满足任一即保存为 feedback）：
- 用户纠正了 AI 的错误做法（"不要这样做"、"改成这样"）
- 一个 bug 被修复，根因是 AI 的固定错误认知（需要下次避免）
- 用户明确确认某种做法正确（"对，就这样"、接受了非显然的选择）

**不**属于 feedback（应归入 project）：
- 项目状态、进展、技术选型
- 截止日期、外部约束
- 架构事实（用了什么库、数据库在哪个端口）

**feedback 写法模板：**
```
[规则本身]
Why: 用户纠正的具体原因 / bug 发生的根因
How to apply: 下次遇到什么情况时启用此规则
```

---

## project — 判断标准

`project` 记录**项目本身的技术事实**，这些信息不在代码里、但影响所有后续决策。

触发条件（满足任一即保存为 project）：
- **技术框架**：使用了哪些语言、框架、库及版本
- **技术选型**：为什么选 A 而不是 B（决策原因）
- **需求/功能边界**：这个项目要做什么、不做什么
- **整体设计**：模块划分、数据模型、API 风格、部署架构
- **环境配置事实**：数据库地址、端口、外部服务 URL

**不**属于 project（应归入 feedback）：
- AI 被纠正的行为规范
- 用户工作偏好（归入 user）

**project 写法模板：**
```
[事实/决策本身]
Why: 选型原因 / 需求背景 / 约束条件
How to apply: 涉及该模块时应参考此记忆
```

---

## reference — 判断标准

`reference` 记录**外部资源的位置指针**，让 AI 知道去哪里查找最新信息，而非把信息本身存进来。

触发条件（满足任一即保存为 reference）：
- Bug/需求跟踪系统：Linear 项目、GitHub Issues、Jira Board 的名称/链接
- 监控/运维入口：Grafana 面板、Datadog dashboard、日志平台 URL
- 文档/规范入口：内网 Wiki、Confluence 页面、API 文档地址
- 沟通渠道：相关 Slack 频道、飞书群、邮件列表
- 数据/报表入口：BI 系统、数据仓库、测试数据库连接信息

**不**属于 reference：
- 把外部文档的内容复制进来（内容会过时，只记位置）
- 代码库内部文件路径（直接读文件即可，不需要 reference）
- 环境变量或配置值（归入 project）

**reference 写法：**
```
[资源名称] 位于 [位置/URL/路径]
用途: 该资源的作用
How to apply: 何时去查这个资源
```
