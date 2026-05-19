# Bark Portfolio Reporter

一个用于个人投资组合收益日报的 Python 小工具。

程序会在 A 股收盘后自动获取持仓行情，计算今日盈亏、累计盈亏，并通过 Bark 推送到 iPhone。

## 功能

- 读取本地 `portfolio.csv` 持仓文件
- 从新浪行情接口获取 A 股 / ETF 实时价格
- 自动判断 A 股交易日，节假日不推送
- 支持每日资产快照
- 支持根据 `trades.csv` 修正加仓 / 减仓后的今日盈亏
- 支持 `trade_input.csv` 自动处理交易记录
- 支持自动估算手续费
- 通过 Bark 推送收益日报
- 支持 cron 定时运行

## 当前能力

程序目前支持：

- A 股 ETF / 股票
- 手动维护或自动更新持仓 CSV
- Bark 推送
- A 股交易日识别
- 今日盈亏计算
- 累计浮盈浮亏计算
- 交易流水修正收益
- 自动估算手续费，默认万 2.5

暂不支持：

- 自动登录券商账户
- 多账户
- 多币种
- 港股 / 美股完整交易日历
- 现金余额管理
- 分红、拆股、转托管等复杂情况

## 项目结构

```text
bark-portfolio-reporter/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── portfolio.example.csv
├── trades.example.csv
├── trade_input.example.csv
├── data/
│   └── .gitkeep
├── logs/
│   └── .gitkeep
└── src/
    ├── main.py
    ├── market_data.py
    ├── market_calendar.py
    ├── calculator.py
    ├── storage.py
    ├── trades.py
    ├── report.py
    └── notifier.py
```

本地运行时会生成这些文件：

```text
portfolio.csv
trades.csv
trade_input.csv
data/snapshots.csv
data/trade_calendar.csv
logs/app.log
```

这些文件包含个人持仓、交易记录、收益快照或运行日志，不建议提交到 Git。

## 安装

### 1. 创建 Conda 环境

```bash
conda create -n bark-portfolio-reporter python=3.11
conda activate bark-portfolio-reporter
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

`requirements.txt` 示例：

```txt
pandas
requests
python-dotenv
exchange_calendars
```

## 配置

### 1. 创建 `.env`

复制示例文件：

```bash
cp .env.example .env
```

`.env` 示例：

```env
BARK_KEY=你的BarkKey
BARK_GROUP=收益日报
BARK_ICON=https://day.app/assets/images/avatar.jpg

COMMISSION_RATE=0.00025
```

字段说明：

| 字段 | 说明 |
|---|---|
| `BARK_KEY` | Bark App 里的推送 key |
| `BARK_GROUP` | Bark 推送分组 |
| `BARK_ICON` | Bark 推送图标，可选 |
| `COMMISSION_RATE` | 佣金率，默认 `0.00025`，即万 2.5 |

不要把 `.env` 提交到 Git。

## 持仓文件

真实持仓文件为：

```text
portfolio.csv
```

格式：

```csv
symbol,name,quantity,cost_price
510300,沪深300ETF示例,1000,3.800
588000,科创50ETF示例,2000,0.950
```

字段说明：

| 字段 | 说明 |
|---|---|
| `symbol` | 证券代码 |
| `name` | 证券名称 |
| `quantity` | 当前持仓数量 |
| `cost_price` | 当前加权成本价 |

`cost_price` 建议保留 3 位小数。

## 交易记录文件

历史交易文件为：

```text
trades.csv
```

格式：

```csv
date,symbol,side,quantity,price,fee,note
2026-05-19,510300,buy,300,3.820,0.29,示例加仓
2026-05-19,588000,buy,500,0.960,0.12,示例建仓
```

字段说明：

| 字段 | 说明 |
|---|---|
| `date` | 交易日期 |
| `symbol` | 证券代码 |
| `side` | 交易方向，`buy` 或 `sell` |
| `quantity` | 成交数量 |
| `price` | 成交价格 |
| `fee` | 手续费 |
| `note` | 备注 |

`trades.csv` 用于计算今日净买入 / 净卖出，从而修正今日盈亏。

## 待处理交易文件

如果启用了自动处理交易功能，可以维护：

```text
trade_input.csv
```

格式：

```csv
date,symbol,name,side,quantity,price,fee,note,processed
2026-05-19,510300,沪深300ETF示例,buy,300,3.820,,示例加仓,no
```

字段说明：

| 字段 | 说明 |
|---|---|
| `date` | 交易日期 |
| `symbol` | 证券代码 |
| `name` | 证券名称 |
| `side` | `buy` 或 `sell` |
| `quantity` | 成交数量 |
| `price` | 成交价格 |
| `fee` | 手续费，可留空 |
| `note` | 备注 |
| `processed` | 是否已处理，新交易填 `no` |

`fee` 可以留空，程序会按 `.env` 中的 `COMMISSION_RATE` 自动估算。

程序处理后会：

1. 自动更新 `portfolio.csv`
2. 自动追加到 `trades.csv`
3. 把 `trade_input.csv` 中对应行的 `processed` 改成 `yes`

## 手续费规则

默认手续费率：

```text
0.00025
```

也就是：

```text
万 2.5
```

计算方式：

```text
手续费 = 成交数量 × 成交价格 × 0.00025
```

例如：

```text
300 × 3.820 × 0.00025 = 0.2865
```

四舍五入后：

```text
0.29 元
```

## 收益计算逻辑

### 累计盈亏

```text
累计盈亏 = 当前市值 - 持仓成本
```

### 累计收益率

```text
累计收益率 = 累计盈亏 / 持仓成本
```

### 今日盈亏

```text
今日盈亏 = 今日当前市值 - 上一交易日当前市值 - 今日交易净投入
```

### 今日交易净投入

买入：

```text
净投入 = 成交金额 + 手续费
```

卖出：

```text
净投入 = -1 × (成交金额 - 手续费)
```

这样加仓不会被误认为盈利，减仓也不会被误认为亏损。

## 运行

手动运行：

```bash
python src/main.py
```

如果今天是交易日，会输出并推送收益日报。

如果今天不是交易日，会输出：

```text
不是 A 股交易日，跳过运行
```

不会抓行情，也不会推送 Bark。

## 定时任务

使用 cron 每个工作日 15:30 自动执行：

```bash
crontab -e
```

加入一行，注意把路径替换成你自己机器上的真实路径：

```bash
30 15 * * 1-5 cd /path/to/bark-portfolio-reporter && /path/to/conda/envs/bark-portfolio-reporter/bin/python src/main.py >> logs/app.log 2>&1
```

可以用下面的命令查看当前项目路径：

```bash
pwd
```

可以用下面的命令查看当前 Python 路径：

```bash
which python
```

查看日志：

```bash
tail -f logs/app.log
```

## 交易日识别

项目使用 `exchange_calendars` 自动生成 A 股交易日历。

生成的缓存文件为：

```text
data/trade_calendar.csv
```

其中：

```text
is_open = 1 交易日
is_open = 0 休市日
```

这个文件是程序自动生成的，不需要手动维护。

旧方案中的：

```text
data/market_holidays.csv
```

不再需要。

## Git 隐私说明

以下文件不建议提交：

```text
.env
portfolio.csv
trades.csv
trade_input.csv
data/
logs/
```

建议只提交示例文件：

```text
portfolio.example.csv
trades.example.csv
trade_input.example.csv
```

`.gitignore` 推荐：

```gitignore
.env
portfolio.csv
trades.csv
trade_input.csv

logs/*
data/*
!logs/.gitkeep
!data/.gitkeep

__pycache__/
*.pyc
.DS_Store
```

## 示例推送内容

```text
📈 今日收益日报

日期：2026-05-19 15:00:00

今日盈亏：+42.18 元
今日收益率：+0.42%
对比日期：2026-05-18

今日交易：净买入 1,146.29 元

持仓成本：5,946.29 元
当前市值：6,018.47 元
累计盈亏：+72.18 元
累计收益率：+1.21%

持仓明细：

沪深300ETF示例
  现价：3.850
  涨跌幅：+0.52%
  盈亏：+50.00 元
  收益率：+1.30%

科创50ETF示例
  现价：0.961
  涨跌幅：+1.16%
  盈亏：+22.18 元
  收益率：+1.17%
```

## 开发状态

当前版本：

```text
v0.4
```

已完成：

- Bark 推送
- 新浪行情
- 每日快照
- A 股交易日判断
- 加仓 / 减仓修正今日盈亏
- 自动估算手续费
- 自动处理交易输入 CSV

后续计划：

- 增加现金余额
- 增加月度收益统计
- 增加收益曲线
- 支持多账户
- 支持更多市场
