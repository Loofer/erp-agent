# 沙箱：让采购分析能执行计算，但不越过数据与文件边界

> 采购分析不只是查询 Motorparts。价格对比、均值、趋势和加权评分需要执行 Python 计算；但执行环境不能借此读取宿主机文件、混入外部数据或把临时产物当成长期记忆。AIO Sandbox 的价值，就是给 `execute` 一块可控的工作区。

在采购分析中，用户可能要求“比较三个供应商的历史采购价并给出趋势”。Motorparts 工具负责返回供应商、物料和订单明细；`execute` 负责基于这些已返回数据聚合、排序和计算。二者不能混用：脚本不能自行抓取外部行情，报告也不能用图像文件绕过前端图表契约。

## 一、沙箱解决的不是权限，而是执行隔离

文件权限与沙箱回答的是两个问题：

| 能力 | 要解决的问题 | 控制对象 |
| --- | --- | --- |
| 文件权限 | 内置文件工具能读写哪个虚拟路径 | `read_file`、`write_file`、`edit_file`、`delete` |
| AIO Sandbox | Shell 和 Python 在哪里运行、能接触什么环境 | `execute`、进程、网络、依赖、临时文件 |

`FilesystemPermission` 不会约束 `execute`。即使禁止向 `/memory/**` 写文件，脚本仍可能访问其执行环境可见的路径或网络。因此 AIO Sandbox 上线后仍需要文件权限，反过来也不能把文件权限当成代码执行隔离。

## 二、采购分析如何使用 `execute`

[`procurement-analysis/SKILL.md`](../../skills/procurement/procurement-analysis/SKILL.md) 为复杂采购分析定义了固定流程：

```text
Motorparts 查询工具
  -> 只取得内部供应商、物料、订单和库存数据
  -> execute 运行 Python 聚合、比较、趋势或加权计算
  -> 需要图表时输出单行 chart JSON
  -> 复杂报告写入 /sandbox/analysis/report_{timestamp}.md
```

具体边界如下：

| 阶段 | 应做什么 | 不应做什么 |
| --- | --- | --- |
| 数据收集 | 调用 Motorparts 工具取得本次分析数据 | 从网络、文件或训练知识补充价格和交期 |
| 数据计算 | 用 Python 标准库，必要时使用已有 `pandas` | 为计算或图表安装新依赖 |
| 图表输出 | 按 `chart_params.md` 输出一行 chart JSON | 使用 matplotlib 等生成 PNG、SVG、PDF、HTML |
| 报告输出 | 复杂报告用 `write_file` 写入 `/analysis/` | 把报告正文塞入 chart JSON，或虚构图片路径 |

这使 `execute` 只承担计算，`write_file` 只承担复杂报告落盘，前端只消费符合契约的 chart JSON。

## 三、为什么目标是 AIO Sandbox

当前 `procurement_analyst.yaml` 已声明 `backend: local_shell`，并在子 Agent loader 中被转换为文件与执行能力。这是采购分析使用 `execute` 的现有接入点，不是最终的隔离方案。

AIO Sandbox 应替代该执行后端，把同样的分析脚本放入隔离环境：

```text
procurement_analyst
  -> Motorparts 工具返回本次数据
  -> AIO Sandbox.execute 处理数据
  -> 返回文本或 chart JSON
  -> write_file 保存复杂报告
```

迁移的目标不是改变采购分析方法，而是收紧执行边界。`execute` 的输入、输出和调用语义应保持兼容；用户长期记忆仍在 `/memories/`，共享规则和技能仍在 `/memory/`、`/skills/`，不能被沙箱临时目录替代。

## 四、AIO Sandbox 应提供的边界

### 1. 工作目录与文件

`/sandbox/` 应映射到 AIO Sandbox 内部的工作目录。Agent 可以在其中创建脚本和临时数据，但不能通过相对路径、挂载或符号链接读取宿主机任意文件。分析报告的 `/analysis/` 路径也必须明确它由哪个 Backend 管理，避免与长期记忆混淆。

### 2. 数据与网络

采购分析只能使用本次 Motorparts 工具返回的数据。默认应阻断出站网络；若确实需要网络能力，必须显式配置允许范围，并避免把 Motorparts Token、数据库密码或模型密钥注入沙箱环境。

### 3. 进程与资源

脚本应有命令超时、CPU、内存、磁盘和进程数限制。失败、死循环或依赖安装不应拖垮 Agent 服务。短任务宜按线程创建并在空闲后回收；只有明确需要复用依赖或工作区时，才考虑更长生命周期并配置 TTL 或清理策略。

### 4. 产物回传

执行结果只回传必要文本、单行 chart JSON 或受控报告文件。日志、代码和文件都是不可信产物，宿主应用在展示、下载或落库前应检查类型、大小和路径。

## 五、源码落点

当前实现的相关位置：

1. [`procurement_analyst.yaml`](../../src/agent/subagents/configs/procurement_analyst.yaml) 声明 `backend: local_shell`，规定 `execute` 用于内部数据计算，复杂报告写入 `/sandbox/analysis/report_{timestamp}.md`。
2. [`loader.py`](../../src/agent/subagents/loader.py) 将 `local_shell` 配置转换为子 Agent 的执行和文件中间件；接入 AIO Sandbox 时应在这里增加或替换 Backend 类型与构造逻辑。
3. [`SKILL.md`](../../skills/procurement/procurement-analysis/SKILL.md) 规定五步分析流程、禁止图像图表文件，并要求图表脚本使用 `chart_params.md` 契约。
4. [`chart_params.md`](../../skills/procurement/procurement-analysis/reference/chart_params.md) 定义 chart JSON 的机器可读格式。

配置、加载器和 Skill 必须同步：只改 YAML 不会创建 AIO Sandbox；只改 Backend 不会让 Agent 遵守“只用内部 Motorparts 数据”和图表输出协议。

## 六、常见失败模式

| 失败模式 | 表现 | 防护方式 |
| --- | --- | --- |
| 将本地执行当成沙箱 | 脚本可读取宿主文件或环境变量 | 将 `local_shell` 接入点替换为 AIO Sandbox Backend |
| 脚本补充外部数据 | 结论混入不可审计的行情或价格 | 默认断网；Skill 明确只使用 Motorparts 工具返回值 |
| 用图片承载图表 | 生成 PNG、SVG 或虚构文件路径 | 只允许 chart JSON；禁止绘图库和图表文件 |
| 图表与报告混在一起 | 前端无法解析，报告内容丢失 | `execute` 只出图表数据，报告由 `write_file` 保存 |
| 临时文件当记忆 | 下个线程找不到或污染长期偏好 | 临时数据留在沙箱，偏好只写 `/memories/` |
| 只配文件权限 | `execute` 仍可访问网络或危险命令 | 同时设置沙箱资源、网络、凭证和命令策略 |

## 七、AIO Sandbox 接入验收

- `procurement_analyst` 的 `execute` 由 AIO Sandbox 执行，不再依赖本地宿主执行环境。
- Python 脚本可完成现有聚合、趋势和评分计算，并保持 chart JSON 契约。
- 默认无法读取宿主机任意路径、非必要环境变量或外部网络。
- 超时、内存、磁盘和进程限制可观测、可回收。
- `/analysis/` 的报告写入和 `/memories/` 的长期偏好相互隔离。
- 测试覆盖 Backend 构造、`execute` 成功和超时、资源回收，以及采购分析图表与报告输出。

> 一句话结论：采购分析的可信边界是“Motorparts 工具取数、沙箱脚本计算、契约 JSON 展示、受控文件写报告”。AIO Sandbox 不改变这条链路，只让其中最有副作用的脚本执行真正离开宿主机。
