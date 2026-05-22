# Bark Portfolio Reporter

一个用于个人投资组合收益日报的 Python 小工具。

程序会在 A 股收盘后自动判断是否交易日，根据 `trades.csv` 重建当前持仓，获取行情，计算今日盈亏和累计盈亏，并通过 Bark 推送到 iPhone。

项目还提供一个 Streamlit GUI，用于查看持仓、编辑交易记录、查看快照、手动运行日报和查看日志。

## 核心流程

```text
trades.csv
    ↓
自动重建 portfolio.csv
    ↓
获取新浪行情
    ↓
计算收益
    ↓
保存每日快照
    ↓
Bark 推送收益日报
```

推荐把 `trades.csv` 作为交易总账来维护。  
`portfolio.csv` 是程序根据交易总账自动生成的当前持仓文件，一般不需要手动修改。

## 功能

- 根据 `trades.csv` 自动重建 `portfolio.csv`
- 从新浪行情接口获取 A 股 / ETF 实时价格
- 自动判断 A 股交易日，节假日不推送
- 支持每日资产快照
- 支持根据交易流水修正加仓 / 减仓后的今日盈亏
- 支持 `trade_input.csv` 自动处理待处理交易，可选
- 支持自动估算手续费
- 通过 Bark 推送收益日报
- 支持 cron 定时运行收益日报
- 支持 Streamlit GUI
- 支持 systemd 常驻运行 GUI

## 当前能力

程序目前支持：

- A 股 ETF / 股票
- Bark 推送
- A 股交易日识别
- 今日盈亏计算
- 累计浮盈浮亏计算
- 交易流水修正收益
- 自动估算手续费，默认万 2.5
- 根据交易流水自动生成当前持仓
- 浏览器 GUI 查看和编辑数据

暂不支持：

- 自动登录券商账户
- 多账户
- 多币种
- 港股 / 美股完整交易日历
- 现金余额管理
- 分红、拆股、转托管等复杂情况
- GUI 登录鉴权

## 项目结构

```text
bark-portfolio-reporter/
├── README.md
├── app.py
├── requirements.txt
├── .env.example
├── .gitignore
├── portfolio.example.csv
├── trades.example.csv
├── trade_input.example.csv
├── .streamlit/
│   └── config.toml
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
streamlit
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

## 推荐使用方式

推荐只维护 `trades.csv`。

每天程序运行时会：

1. 读取 `trades.csv`
2. 按交易日期从早到晚重建当前持仓
3. 自动生成 / 覆盖 `portfolio.csv`
4. 获取行情
5. 计算收益
6. 发送 Bark 推送

因此：

```text
trades.csv      手动维护，作为交易总账
portfolio.csv   程序自动生成，一般不要手动改
```


## 交易总账：trades.csv

真实交易总账文件为：

```text
trades.csv
```

格式：

```csv
date,symbol,side,quantity,price,fee,note
2026-05-19,510300,buy,300,3.820,,示例加仓
2026-05-19,588000,buy,500,0.960,,示例建仓
```

字段说明：

| 字段 | 说明 |
|---|---|
| `date` | 交易日期，格式 `YYYY-MM-DD` |
| `symbol` | 证券代码 |
| `side` | 交易方向，`buy` 或 `sell` |
| `quantity` | 成交数量 |
| `price` | 成交价格 |
| `fee` | 手续费，可留空 |
| `note` | 备注 |

`fee` 可以留空。留空时，程序会根据 `.env` 中的 `COMMISSION_RATE` 自动估算手续费。

### 买入示例

```csv
date,symbol,side,quantity,price,fee,note
2026-05-19,510300,buy,300,3.820,,加仓
```

### 卖出示例

```csv
date,symbol,side,quantity,price,fee,note
2026-05-20,510300,sell,100,3.900,,减仓
```

卖出时，程序会减少持仓数量，并用卖出成交净额冲减剩余持仓成本。  
如果卖出价低于持仓成本，剩余持仓成本价会上升；如果卖出价高于持仓成本，剩余持仓成本价会下降。

## 当前持仓：portfolio.csv

真实持仓文件为：

```text
portfolio.csv
```

它由程序根据 `trades.csv` 自动生成，不建议手动编辑。

自动生成示例：

```csv
symbol,name,quantity,cost_price
510300,沪深300ETF,300.0,3.820
588000,科创50ETF,500.0,0.960
```

字段说明：

| 字段 | 说明 |
|---|---|
| `symbol` | 证券代码 |
| `name` | 证券名称 |
| `quantity` | 当前持仓数量 |
| `cost_price` | 当前持仓成本价 |

如果交易总账中没有名称，程序会先用代码生成持仓，随后通过新浪行情返回的名称自动补全 `portfolio.csv` 中的 `name`。

`cost_price` 建议保留 3 位小数。


## 可选：待处理交易 trade_input.csv

如果不想直接编辑 `trades.csv`，也可以维护：

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

程序处理后会：

1. 自动追加到 `trades.csv`
2. 自动更新 / 重建 `portfolio.csv`
3. 把 `trade_input.csv` 中对应行的 `processed` 改成 `yes`

如果同一笔交易已经存在于 `trades.csv`，程序会跳过重复追加，避免重复更新持仓。

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

如果你知道实际手续费，也可以在 CSV 中手动填写实际金额。  
如果不知道，留空即可。

规则：

```text
fee 为空 / auto / -- / nan / none → 自动计算
fee 填数字                       → 使用填写的数字
```

## 收益计算逻辑

### 持仓成本

```text
持仓成本 = 当前持仓数量 × 当前持仓成本价
```

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

如果今天没有交易，程序会优先使用行情接口返回的涨跌额计算：

```text
今日盈亏 = Σ(当前持仓数量 × 今日涨跌额)
```

这样即使后来修正了历史交易记录，也不会把历史持仓变化误算成当天盈亏。

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


## 运行收益日报

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

## 定时任务：cron 自动推送收益日报

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

查看 cron 日志：

```bash
tail -f logs/app.log
```

也可以在 Streamlit GUI 的“定时任务”页面管理这条任务。页面会在当前用户的
crontab 中维护下面这个带标记的区块，只替换标记之间的内容，不会改动其他
cron 任务：

```cron
# bark-portfolio-reporter BEGIN
30 15 * * 1-5 cd /path/to/bark-portfolio-reporter && /path/to/conda/envs/bark-portfolio-reporter/bin/python src/main.py >> logs/app.log 2>&1
# bark-portfolio-reporter END
```

注意：GUI 必须使用同一个 Linux 用户运行，才能修改该用户的 crontab。

## Streamlit GUI

项目提供浏览器 GUI：

```bash
streamlit run app.py
```

如果只允许本机访问：

```bash
streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

如果需要局域网访问，可以绑定局域网 IP：

```bash
streamlit run app.py --server.address 192.168.x.x --server.port 8501
```

访问地址示例：

```text
http://192.168.x.x:8501
```

GUI 功能包括：

- 总览
- 编辑 `trades.csv`
- 查看 `portfolio.csv`
- 查看 `snapshots.csv`
- 手动运行收益日报
- 查看日志

注意：Streamlit 默认没有登录鉴权，不建议直接暴露到公网。

## Streamlit 配置

可以创建：

```text
.streamlit/config.toml
```

示例：

```toml
[server]
address = "127.0.0.1"
port = 8501

[browser]
gatherUsageStats = false
```

如果只在局域网使用，可以把 `address` 改成你的局域网 IP，例如：

```toml
[server]
address = "192.168.x.x"
port = 8501

[browser]
gatherUsageStats = false
```


## systemd 常驻运行 GUI

如果希望 GUI 一直运行，并且开机自启，推荐使用 systemd。

### 1. 创建服务文件

```bash
sudo nano /etc/systemd/system/bark-portfolio-gui.service
```

示例内容，注意把路径和用户名改成你自己的：

```ini
[Unit]
Description=Bark Portfolio Reporter Streamlit GUI
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/bark-portfolio-reporter
ExecStart=/path/to/conda/envs/bark-portfolio-reporter/bin/streamlit run app.py --server.address 192.168.x.x --server.port 8501
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 2. 启动服务

```bash
sudo systemctl daemon-reload
sudo systemctl start bark-portfolio-gui
```

### 3. 设置开机自启

```bash
sudo systemctl enable bark-portfolio-gui
```

### 4. 查看状态

```bash
sudo systemctl status bark-portfolio-gui
```

正常时应看到：

```text
Active: active (running)
```

### 5. 查看 GUI 日志

```bash
journalctl -u bark-portfolio-gui -f
```

### 6. 重启 / 停止 GUI

```bash
sudo systemctl restart bark-portfolio-gui
sudo systemctl stop bark-portfolio-gui
sudo systemctl start bark-portfolio-gui
```

注意：如果已经用 systemd 启动 GUI，不要再手动执行 `streamlit run app.py`，否则可能出现端口被占用。


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
.streamlit/secrets.toml
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
v0.6
```

已完成：

- Bark 推送
- 新浪行情
- 每日快照
- A 股交易日判断
- 根据 `trades.csv` 自动重建 `portfolio.csv`
- 加仓 / 减仓修正今日盈亏
- 自动估算手续费
- 自动处理交易输入 CSV
- 重复交易保护
- 自动补全持仓名称
- Streamlit GUI
- systemd 常驻运行 GUI

后续计划：

- 增加现金余额
- 增加月度收益统计
- 增加收益曲线
- 支持多账户
- 支持更多市场
- GUI 登录鉴权
