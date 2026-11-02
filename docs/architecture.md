# 架构

## 数据流

```text
              ┌────────────┐
  Akshare ───▶│ data.fetch │──┐
  Tushare ───▶└────────────┘  │
                              ▼
                    ┌──────────────────┐
  本地 CSV ────────▶│ data.convert     │──▶ ~/.kronos/data/*_kronos.csv
                    │ 归一 / 聚合 / 去重│
                    └──────────────────┘
                              │
                 ┌────────────┼─────────────┐
                 ▼            ▼             ▼
          data.validate  heatmap.market  evaluation.runner
          质量报告         HTML 云图        RankIC / 净值
```

`fetch` 只负责「拿到数据」，`convert` 只负责「变成标准格式」，`validate` 只负责「判断好坏」。三者独立，任何一层都可以被替换。

## 模块职责

| 模块 | 职责 | 不做什么 |
|------|------|----------|
| `config.py` | 解析环境变量、拼路径、代码规范化 | 不读写数据 |
| `names.py` | 代码 → 中文名称，内置表 + 覆盖文件 | 不联网（除 `refresh_names`） |
| `data/fetch.py` | 数据源链、限速、重试 | 不落盘 |
| `data/convert.py` | 字段归一、周期聚合 | 不做质量判断 |
| `data/validate.py` | 缺列/重复/断档/OHLC/周末检查 | 不修改数据 |
| `heatmap/market.py` | 计算 `Snapshot`、渲染 HTML | 不画图、不打开浏览器 |
| `heatmap/dividend.py` | 红利打分、卡片渲染 | 不抓分红数据 |
| `heatmap/theme.py` | 阈值、配色、CSS/JS | 不含业务逻辑 |
| `evaluation/metrics.py` | 纯数学：RankIC、净值、回撤 | 不加载模型 |
| `evaluation/runner.py` | 交易日历、批预测、汇总 | 不含指标公式 |
| `predict.py` | 加载 Kronos、预测、对齐 | 不画图 |
| `plot.py` | 预测图 | 不读模型 |

## 关键设计

### 1. 配置即环境

没有任何绝对路径写死在代码里。`Settings.load()` 是唯一的路径来源，CLI 的 `--data-dir` / `--out-dir` 通过 `with_data_dir()` 产生新实例，而不是改全局状态。这让测试可以用 `tmp_path`，也让同一个进程能处理多个数据集。

### 2. 纯函数优先

`compute_snapshot(frame)`、`spearman(a, b)`、`net_value(returns)` 都是纯函数：输入 DataFrame/Series，输出 dataclass 或 float。I/O 留在 `load_snapshots`、`run_evaluation` 这类边界函数里。

### 3. 渲染与计算解耦

`Snapshot` 持有四个周期的涨跌幅与成交量，`render_html` 只做字符串拼接。换配色、加搜索、改排序都不影响数值；改动阈值只动 `theme.BUCKETS`。

### 4. 可选依赖延迟加载

`akshare`、`tushare`、`torch` 都在函数内部 import。基础安装只装 pandas/numpy/matplotlib，CI 不需要下载 2GB 的 torch。

### 5. 安全边界

- 所有插入 HTML 的文本经过 `html.escape`。
- 代码名称、表头等外部字符串在渲染前转义。
- 不执行任何来自数据文件的代码。
- token 只从环境变量读取，不写入日志、不落盘。

## 扩展点

**加数据源**：实现 `fetch()` 或新增 `_provider_xxx()`，返回标准列即可。

**加指标**：在 `Snapshot` 增加字段并在 `compute_snapshot` 计算，`_cell` 里展示；同步更新 `theme.BUCKETS`。

**加视图**：`render_html` 里新增一个 `grid-<metric>`，并在 `METRICS` 注册。

**加评测维度**：`runner.run_evaluation` 的 `records` 追加字段，`summarize` 汇总。
