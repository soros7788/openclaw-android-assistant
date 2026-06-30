import json
import pandas as pd

stock_code = "sh000001"

# 解析日线
with open("/workspace/shz_daily.json", "r", encoding="utf-8") as f:
    data = json.load(f)

klines = data["data"][stock_code].get("qfqday", data["data"][stock_code].get("day", []))
rows = []
for item in klines:
    rows.append({
        "日期": item[0],
        "开盘": float(item[1]),
        "收盘": float(item[2]),
        "最高": float(item[3]),
        "最低": float(item[4]),
        "成交量": float(item[5]),
    })
df_d = pd.DataFrame(rows)
print(f"日线数据: {len(df_d)}条")
print(df_d.tail(5).to_string())
df_d.to_csv("/workspace/sh000001_daily.csv", index=False, encoding="utf-8-sig")

# 解析周线
with open("/workspace/shz_week.json", "r", encoding="utf-8") as f:
    data = json.load(f)

klines = data["data"][stock_code].get("qfqweek", data["data"][stock_code].get("week", []))
rows = []
for item in klines:
    rows.append({
        "日期": item[0],
        "开盘": float(item[1]),
        "收盘": float(item[2]),
        "最高": float(item[3]),
        "最低": float(item[4]),
        "成交量": float(item[5]),
    })
df_w = pd.DataFrame(rows)
print(f"\n周线数据: {len(df_w)}条")
print(df_w.tail(5).to_string())
df_w.to_csv("/workspace/sh000001_week.csv", index=False, encoding="utf-8-sig")

# 解析月线
with open("/workspace/shz_month.json", "r", encoding="utf-8") as f:
    data = json.load(f)

klines = data["data"][stock_code].get("qfqmonth", data["data"][stock_code].get("month", []))
rows = []
for item in klines:
    rows.append({
        "日期": item[0],
        "开盘": float(item[1]),
        "收盘": float(item[2]),
        "最高": float(item[3]),
        "最低": float(item[4]),
        "成交量": float(item[5]),
    })
df_m = pd.DataFrame(rows)
print(f"\n月线数据: {len(df_m)}条")
print(df_m.tail(5).to_string())
df_m.to_csv("/workspace/sh000001_month.csv", index=False, encoding="utf-8-sig")
