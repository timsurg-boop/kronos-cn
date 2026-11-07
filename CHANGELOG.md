# Changelog

所有值得记录的变更都写在这里。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)。

## [0.1.0] - 2026-11-03

首个公开版本，从个人研究脚本整理为可安装的工具包。

### 新增

- `kronos-cn` 命令行：`demo` / `validate` / `heatmap` / `dividend` / `fetch` / `predict` / `eval` / `names`。
- 市场云图：周/月/季/年四周期，颜色=涨跌幅，面积=成交量，支持搜索、排序、切换周期。
- 两套配色：`cn`（红涨绿跌，默认）与 `intl`（绿涨红跌）。
- 红利热力图：稳健红利分、核心/观察/弱三档。
- K 线三联图：日/周/月蜡烛图 + MA5/10/20 + 成交量，一条命令出图。
- 数据体检：缺列、重复日期、断档、OHLC 异常、零成交量、周末行。
- 滚动 RankIC 评测：逐期 CSV、净值曲线、多空差、趋势闸门。
- 内置 5600+ 条代码名称表与 31 个标的的样例数据。
- 28 个单元测试，GitHub Actions 覆盖 Python 3.10–3.12。

### 变更

- 所有路径改为环境变量驱动，移除硬编码的 `~/Desktop/Kronos`。
- 数据抓取改为「Akshare 优先、Tushare 兜底」，token 只从环境变量读取。
- 渲染与指标计算解耦，`Snapshot` 可单独测试。
