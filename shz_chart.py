import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

df = pd.read_csv("/workspace/sh000001_daily.csv")
df['日期'] = pd.to_datetime(df['日期'])

# 只画最近6个月的
df = df[df['日期'] >= '2026-01-01'].copy()

# 分型数据
tops = [
    ('2026-01-16', 4190.87),
    ('2026-03-06', 4197.23),
    ('2026-05-14', 4258.86),
    ('2026-06-03', 4107.05),
    ('2026-06-23', 4175.35),
]

bottoms = [
    ('2026-02-06', 4002.78),
    ('2026-03-27', 3794.68),
    ('2026-04-03', 3871.30),
    ('2026-06-02', 4032.58),
    ('2026-06-08', 3927.85),
]

fig, ax = plt.subplots(figsize=(16, 10))

# K线(用收盘价线+高低范围填充)
ax.plot(df['日期'], df['收盘'], color='#1565C0', linewidth=1.5, label='Close', alpha=0.9)
ax.fill_between(df['日期'], df['最低'], df['最高'], color='#1565C0', alpha=0.1)

# 顶分型
for date_str, price in tops:
    date = pd.to_datetime(date_str)
    if date >= df['日期'].min() and date <= df['日期'].max():
        ax.scatter([date], [price], color='#E53935', s=120, zorder=5, marker='v')
        ax.annotate(f'T\n{price:.0f}', xy=(date, price), xytext=(0, 15),
                    textcoords='offset points', ha='center', fontsize=8,
                    color='#E53935', fontweight='bold')

# 底分型
for date_str, price in bottoms:
    date = pd.to_datetime(date_str)
    if date >= df['日期'].min() and date <= df['日期'].max():
        ax.scatter([date], [price], color='#43A047', s=120, zorder=5, marker='^')
        ax.annotate(f'B\n{price:.0f}', xy=(date, price), xytext=(0, -25),
                    textcoords='offset points', ha='center', fontsize=8,
                    color='#43A047', fontweight='bold')

# 笔的连接
bi_lines = [
    ('2026-02-06', 4002.78, '2026-03-06', 4197.23, 'up'),
    ('2026-03-06', 4197.23, '2026-03-27', 3794.68, 'down'),
    ('2026-03-27', 3794.68, '2026-05-14', 4258.86, 'up'),
    ('2026-05-14', 4258.86, '2026-06-08', 3927.85, 'down'),
    ('2026-06-08', 3927.85, '2026-06-23', 4175.35, 'up'),
]

for d1, p1, d2, p2, dr in bi_lines:
    color = '#43A047' if dr == 'up' else '#E53935'
    ax.plot([pd.to_datetime(d1), pd.to_datetime(d2)], [p1, p2],
            color=color, linewidth=2, linestyle='--', alpha=0.7)

# 当前价格
last_date = df.iloc[-1]['日期']
last_price = df.iloc[-1]['收盘']
ax.axhline(y=last_price, color='gray', linestyle=':', alpha=0.5)
ax.annotate(f'Now: {last_price:.0f}', xy=(last_date, last_price), xytext=(-80, 10),
            textcoords='offset points', fontsize=10, color='#333',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7))

# 支撑阻力
ax.axhline(y=4258.86, color='#E53935', linestyle='-.', alpha=0.5, linewidth=1)
ax.text(df['日期'].iloc[0], 4258.86, ' Resistance 4259', va='bottom', fontsize=9, color='#E53935')

ax.axhline(y=3927.85, color='#43A047', linestyle='-.', alpha=0.5, linewidth=1)
ax.text(df['日期'].iloc[0], 3927.85, ' Support 3928', va='bottom', fontsize=9, color='#43A047')

ax.set_title('Shanghai Composite Index - Chan Theory Structure Analysis (Daily)', fontsize=14, fontweight='bold')
ax.set_xlabel('Date', fontsize=11)
ax.set_ylabel('Index', fontsize=11)
ax.legend(loc='lower right')
ax.grid(True, alpha=0.3)

ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
plt.xticks(rotation=45)

plt.tight_layout()
plt.savefig('/workspace/shanghai_index_chart.png', dpi=150, bbox_inches='tight')
print("图表已保存至: /workspace/shanghai_index_chart.png")
