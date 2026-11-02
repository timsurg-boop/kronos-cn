# 贡献指南

## 开发环境

```bash
git clone https://github.com/timsurg-boop/kronos-cn.git
cd kronos-cn
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

需要抓数据时再装 `.[fetch]`，需要跑预测再装 `.[predict]`。

## 提交前

```bash
ruff check .
pytest
kronos-cn demo --out /tmp/heatmap.html
```

三条都通过再开 PR。CI 会在 Python 3.10 / 3.11 / 3.12 上重复这三步。

## 代码约定

1. 一个模块只做一件事，I/O 与计算分离。
2. 数值逻辑写成纯函数，放在 `metrics.py` 或 `Snapshot` 里，便于单测。
3. 新增外部依赖前先问：标准库或现有依赖能不能做？
4. 所有进入 HTML 的文本必须 `html.escape`。
5. 不提交任何 token、密钥、个人路径或真实账户数据。

## 新增数据源

1. 在 `data/fetch.py` 增加 `_provider_xxx()`，返回标准列。
2. 加进 `fetch()` 的 provider 链，保持「免费源优先，付费源兜底」。
3. 捕获异常并记录到 `errors`，不要静默失败。
4. 补一个不联网的单测（mock 返回固定 DataFrame）。

## 新增指标或视图

1. `Snapshot` 加字段，`compute_snapshot` 计算。
2. `heatmap/theme.py` 的 `BUCKETS` 加阈值，`METRIC_LABELS` 加名称。
3. `market.METRICS` 注册，`render_html` 会自动生成第五个网格。
4. 更新 `docs/` 与 README 的命令说明。

## 提交信息

用祈使句，一句话说清改了什么：

```text
add weekly aggregation guard for short histories
fix heatmap name overflow on small cells
docs: explain RankIC gate
```

## PR 检查清单

- [ ] `ruff check .` 通过
- [ ] `pytest` 通过
- [ ] 新功能有测试
- [ ] 没有提交 `*.csv`（样例数据除外）、`.env`、模型权重
- [ ] README / docs 已同步
