import pandas as pd
import numpy as np

def find_fractals(df):
    highs = df['最高'].values
    lows = df['最低'].values
    n = len(df)
    tops = []
    bottoms = []
    for i in range(2, n - 2):
        if (highs[i] >= highs[i-1] and highs[i] >= highs[i+1] and
            highs[i] >= highs[i-2] and highs[i] >= highs[i+2]):
            if lows[i] > lows[i-1] or lows[i] > lows[i+1]:
                tops.append((i, highs[i], lows[i]))
        if (lows[i] <= lows[i-1] and lows[i] <= lows[i+1] and
            lows[i] <= lows[i-2] and lows[i] <= lows[i+2]):
            if highs[i] < highs[i-1] or highs[i] < highs[i+1]:
                bottoms.append((i, highs[i], lows[i]))
    return tops, bottoms

def merge_fractals(tops, bottoms):
    all_f = []
    for idx, h, l in tops:
        all_f.append((idx, h, l, 'top'))
    for idx, h, l in bottoms:
        all_f.append((idx, h, l, 'bottom'))
    all_f.sort(key=lambda x: x[0])
    if not all_f:
        return []
    merged = [all_f[0]]
    for f in all_f[1:]:
        last = merged[-1]
        if f[3] == last[3]:
            if f[3] == 'top' and f[1] > last[1]:
                merged[-1] = f
            elif f[3] == 'bottom' and f[2] < last[2]:
                merged[-1] = f
        else:
            merged.append(f)
    return merged

def build_bi(merged, df):
    bi = []
    for i in range(len(merged) - 1):
        f1, f2 = merged[i], merged[i+1]
        if f1[3] == f2[3]:
            continue
        direction = 'up' if f1[3] == 'bottom' else 'down'
        start_price = f1[2] if f1[3] == 'bottom' else f1[1]
        end_price = f2[1] if f2[3] == 'top' else f2[2]
        if direction == 'up' and end_price <= start_price:
            continue
        if direction == 'down' and end_price >= start_price:
            continue
        bi.append({
            'direction': direction,
            'start_idx': f1[0],
            'end_idx': f2[0],
            'start_price': start_price,
            'end_price': end_price,
            'high': max(start_price, end_price),
            'low': min(start_price, end_price),
            'start_date': df.iloc[f1[0]]['日期'],
            'end_date': df.iloc[f2[0]]['日期'],
        })
    return bi

def build_duan(bi_list):
    if len(bi_list) < 4:
        return []
    duan = []
    i = 0
    while i <= len(bi_list) - 4:
        seg_dir = bi_list[i]['direction']
        seg_indices = [i]
        j = i + 1
        while j < len(bi_list):
            if bi_list[j]['direction'] == seg_dir:
                seg_indices.append(j)
            else:
                first_bi = bi_list[seg_indices[0]]
                if seg_dir == 'up':
                    if bi_list[j]['low'] < first_bi['low']:
                        break
                else:
                    if bi_list[j]['high'] > first_bi['high']:
                        break
                seg_indices.append(j)
            j += 1
        same_dir = [idx for idx in seg_indices if bi_list[idx]['direction'] == seg_dir]
        if len(same_dir) >= 3:
            start_bi = bi_list[same_dir[0]]
            end_bi = bi_list[same_dir[-1]]
            duan.append({
                'direction': seg_dir,
                'start_idx': start_bi['start_idx'],
                'end_idx': end_bi['end_idx'],
                'start_price': start_bi['start_price'],
                'end_price': end_bi['end_price'],
                'start_date': start_bi['start_date'],
                'end_date': end_bi['end_date'],
                'high': max(bi_list[idx]['high'] for idx in seg_indices),
                'low': min(bi_list[idx]['low'] for idx in seg_indices),
                'bi_count': len(seg_indices),
            })
            i = same_dir[-1] + 1
        else:
            i += 1
    return duan

def find_zhongshu(duan_list):
    if len(duan_list) < 3:
        return []
    zhongshu = []
    for i in range(len(duan_list) - 2):
        d1, d2, d3 = duan_list[i], duan_list[i+1], duan_list[i+2]
        if d1['direction'] == d2['direction'] or d2['direction'] == d3['direction']:
            continue
        oh = min(d1['high'], d2['high'], d3['high'])
        ol = max(d1['low'], d2['low'], d3['low'])
        if oh > ol:
            zhongshu.append({
                'start_idx': d1['start_idx'],
                'end_idx': d3['end_idx'],
                'high': oh,
                'low': ol,
                'center': (oh + ol) / 2,
                'start_date': d1['start_date'],
                'end_date': d3['end_date'],
            })
    return zhongshu

def check_beichi(duan_list, df):
    beichi = []
    for i in range(2, len(duan_list)):
        d1, d2 = duan_list[i-2], duan_list[i]
        if d1['direction'] != d2['direction']:
            continue
        amp1 = abs(d1['end_price'] - d1['start_price'])
        amp2 = abs(d2['end_price'] - d2['start_price'])
        if amp2 < amp1 * 0.85:
            beichi.append({
                'type': '下跌背驰(买点)' if d1['direction'] == 'down' else '上涨背驰(卖点)',
                'direction': d1['direction'],
                'prev_amp': amp1,
                'curr_amp': amp2,
                'prev_date': d1['end_date'],
                'curr_date': d2['end_date'],
                'curr_price': d2['end_price'],
            })
    return beichi

def analyze(df, name):
    print(f"\n{'='*60}")
    print(f"【{name}分析】 数据: {len(df)}条, 范围: {df.iloc[0]['日期']}~{df.iloc[-1]['日期']}")
    print(f"{'='*60}")
    tops, bottoms = find_fractals(df)
    print(f"顶分型: {len(tops)}, 底分型: {len(bottoms)}")
    merged = merge_fractals(tops, bottoms)
    print(f"合并分型: {len(merged)}")
    if merged:
        print("最近分型:")
        for f in merged[-8:]:
            t = "顶" if f[3] == 'top' else "底"
            print(f"  {t} {df.iloc[f[0]]['日期']} 高{f[1]:.2f} 低{f[2]:.2f}")
    bi = build_bi(merged, df)
    print(f"\n笔: {len(bi)}")
    if bi:
        for b in bi[-8:]:
            print(f"  {b['direction']} {b['start_date']}({b['start_price']:.2f}) -> {b['end_date']}({b['end_price']:.2f})")
    duan = build_duan(bi)
    print(f"\n线段: {len(duan)}")
    if duan:
        for d in duan[-5:]:
            print(f"  {d['direction']} {d['start_date']}({d['start_price']:.2f}) -> {d['end_date']}({d['end_price']:.2f})")
    zs = find_zhongshu(duan)
    print(f"\n中枢: {len(zs)}")
    if zs:
        for z in zs[-3:]:
            print(f"  [{z['low']:.2f}, {z['high']:.2f}] {z['start_date']}~{z['end_date']}")
    bc = check_beichi(duan, df)
    print(f"\n背驰: {len(bc)}")
    if bc:
        for b in bc[-3:]:
            print(f"  {b['type']}: {b['curr_date']} 幅度{b['curr_amp']:.2f}(前{b['prev_amp']:.2f})")
    trend = "无法判断"
    if duan:
        last = duan[-1]
        if zs:
            lz = zs[-1]
            if last['end_price'] > lz['high']:
                trend = "上涨趋势(离开中枢)"
            elif last['end_price'] < lz['low']:
                trend = "下跌趋势(离开中枢)"
            else:
                trend = "中枢震荡"
        else:
            trend = "上涨" if last['direction'] == 'up' else "下跌"
    print(f"\n趋势: {trend}")
    return {
        'tops': tops, 'bottoms': bottoms, 'merged': merged,
        'bi': bi, 'duan': duan, 'zhongshu': zs, 'beichi': bc,
        'trend': trend,
        'last_price': df.iloc[-1]['收盘'],
        'last_date': df.iloc[-1]['日期'],
    }

if __name__ == "__main__":
    df_d = pd.read_csv("/workspace/sh000001_daily.csv")
    df_w = pd.read_csv("/workspace/sh000001_week.csv")
    df_m = pd.read_csv("/workspace/sh000001_month.csv")

    print("上证指数 缠论分析")
    print(f"最新: {df_d.iloc[-1]['收盘']:.2f} ({df_d.iloc[-1]['日期']})")

    m = analyze(df_m, "月线")
    w = analyze(df_w, "周线")
    d = analyze(df_d, "日线")

    print(f"\n{'='*60}")
    print("【综合】")
    print(f"{'='*60}")
    print(f"月线: {m['trend']} | {len(m['duan'])}段 {len(m['zhongshu'])}中枢 {len(m['beichi'])}背驰")
    print(f"周线: {w['trend']} | {len(w['duan'])}段 {len(w['zhongshu'])}中枢 {len(w['beichi'])}背驰")
    print(f"日线: {d['trend']} | {len(d['duan'])}段 {len(d['zhongshu'])}中枢 {len(d['beichi'])}背驰")
