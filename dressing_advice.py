# -*- coding: utf-8 -*-
"""
26度穿衣法则 - 穿衣建议程序（按温度区间成套搭配）

原理：当日气温 + 衣物保暖度 = 26℃（人体体感舒适温度）
本版不再硬凑数值，而是按温度区间直接给出成套搭配。

用法：
    python dressing_advice.py 18          # 手动输入气温
    python dressing_advice.py             # 获取默认城市（临沂）气温（需联网）
    python dressing_advice.py --city 北京 # 指定城市（需联网）
"""

import sys
import json
import urllib.request
import urllib.parse

COMFORT = 26  # 人体舒适温度
DEFAULT_CITY = "临沂"  # 默认城市（双击无参运行时使用）

# 温度区间 → 成套搭配
# (下限, 上限, 搭配, 小贴士)  上限不包含（即 [lo, hi)），首尾用 inf 兜底
OUTFITS = [
    (28, float("inf"), "短袖T恤 + 短裤/短裙", "炎热，注意防晒补水"),
    (24, 28, "短袖T恤 + 薄长裤/薄裙", "体感舒适，早晚可备件薄外套"),
    (20, 24, "短袖T恤 + 薄外套", "或长袖衬衫单穿，早晚微凉套外套"),
    (16, 20, "长袖衬衫/薄卫衣 + 薄外套/风衣", "微凉，注意脖子和手腕保暖"),
    (11, 16, "毛衣/针织衫 + 风衣/薄外套", "偏凉，内搭可加打底"),
    (6, 11, "毛衣 + 棉服/夹克", "冷，建议加围巾"),
    (1, 6, "保暖内衣 + 毛衣 + 棉服/薄羽绒服", "寒冷，注意手脚保暖"),
    (float("-inf"), 1, "保暖内衣 + 厚毛衣 + 厚羽绒服/呢大衣", "严寒，尽量减少户外停留"),
]


def pick_outfit(temp: float):
    """根据气温返回对应的成套搭配。"""
    for lo, hi, outfit, tip in OUTFITS:
        if lo <= temp < hi:
            return outfit, tip
    return "短袖T恤", ""


def fetch_temperature(city: str = None):
    """通过 wttr.in 免费接口获取当前气温（无需 API Key）。
    返回 (气温, 地区名, 省份)。"""
    base = "https://wttr.in/"
    target = urllib.parse.quote(city) if city else ""
    url = f"{base}{target}?format=j1"
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    current = data["current_condition"][0]
    temp = float(current["temp_C"])
    na = data["nearest_area"][0]
    area = na["areaName"][0]["value"]
    region = na["region"][0]["value"]
    return temp, area, region


def main():
    args = sys.argv[1:]
    temp = None
    city = None

    # 解析参数
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--city" and i + 1 < len(args):
            city = args[i + 1]
            i += 2
        else:
            try:
                temp = float(a)
            except ValueError:
                print(f"无法识别的参数: {a}")
                return
            i += 1

    if temp is None:
        if city is None:
            city = DEFAULT_CITY
        try:
            temp, area, region = fetch_temperature(city)
            print(f"已获取「{city}」实时气温: {temp}℃（解析到 {area}, {region}）")
        except Exception as e:
            print(f"获取「{city}」气温失败（{e}）")
            try:
                temp = float(input("请输入当日气温（℃）: "))
            except (ValueError, EOFError):
                print("未获取到有效气温，程序退出。")
                return

    outfit, tip = pick_outfit(temp)
    need = COMFORT - temp

    print(f"\n{'=' * 40}")
    print(f"今日气温: {temp}℃ | 舒适温度: {COMFORT}℃")
    print(f"参考需保暖度: {need:.0f}℃")
    print(f"{'=' * 40}")
    print(f"建议搭配: {outfit}")
    if tip:
        print(f"小贴士: {tip}")
    print(f"{'=' * 40}\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
    # 双击运行时避免窗口一闪而过
    try:
        input("\n按回车键退出...")
    except EOFError:
        pass
