# -*- coding: utf-8 -*-
"""
穿衣建议 · 26度穿衣法则（桌面 GUI 版）

- 双击运行，弹出窗口显示「默认城市实时气温 + 成套穿衣建议」
- 平时不驻留后台、不占用内存；关闭窗口即彻底退出
- 支持手动指定城市 / 手动输入气温（离线可用）
- 除气温外，同时展示风力、紫外线强度（晒不晒）、湿度，并动态补充防风/防晒/带伞提示
"""

import json
import threading
import urllib.request
import urllib.parse
import tkinter as tk

COMFORT = 26
DEFAULT_CITY = "临沂"

# 配色
BG = "#f4f6f9"        # 窗口背景
CARD = "#ffffff"      # 卡片背景
BORDER = "#e6e9ef"    # 卡片边框
ACCENT = "#3b82f6"    # 主色
ACCENT_DARK = "#2563eb"
TEXT = "#1f2937"      # 主文字
MUTED = "#7c8493"     # 次要文字
CHIP_BG = "#eef2f7"   # 信息小标签底色
FONT = "Microsoft YaHei UI"

# 温度区间 → 成套搭配 (下限, 上限, 搭配, 小贴士)
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

# 常见天气英文 → 中文
WEATHER_ZH = {
    "Sunny": "晴", "Clear": "晴", "Partly cloudy": "多云", "Cloudy": "阴",
    "Overcast": "阴", "Mist": "薄雾", "Fog": "雾", "Light rain": "小雨",
    "Moderate rain": "中雨", "Heavy rain": "大雨", "Light drizzle": "毛毛雨",
    "Patchy rain nearby": "局部阵雨", "Light snow": "小雪", "Snow": "雪",
    "Moderate snow": "中雪", "Heavy snow": "大雪",
}

# 16 方位风向 → 中文
WIND_DIR_ZH = {
    "N": "北", "NNE": "东北偏北", "NE": "东北", "ENE": "东北偏东",
    "E": "东", "ESE": "东南偏东", "SE": "东南", "SSE": "东南偏南",
    "S": "南", "SSW": "西南偏南", "SW": "西南", "WSW": "西南偏西",
    "W": "西", "WNW": "西北偏西", "NW": "西北", "NNW": "西北偏北",
}

# 蒲福风级阈值（km/h 上限，依次对应 0~12 级）
WIND_SCALE_THRESHOLD = [1, 6, 12, 20, 29, 39, 50, 62, 75, 89, 103, 118]


def pick_outfit(temp):
    for lo, hi, outfit, tip in OUTFITS:
        if lo <= temp < hi:
            return outfit, tip
    return "短袖T恤", ""


def temp_style(temp):
    """根据气温返回 (表情, 颜色)。"""
    if temp >= 28:
        return "🥵", "#ef4444"
    if temp >= 24:
        return "😎", "#f97316"
    if temp >= 20:
        return "🙂", "#16a34a"
    if temp >= 16:
        return "🍂", "#d97706"
    if temp >= 11:
        return "🧥", "#0284c7"
    if temp >= 6:
        return "❄️", "#2563eb"
    if temp >= 1:
        return "🥶", "#4f46e5"
    return "🧊", "#1e3a8a"


def wind_scale(kmph):
    """风速(km/h) → 蒲福风级 0~12。"""
    for lv, thr in enumerate(WIND_SCALE_THRESHOLD):
        if kmph < thr:
            return lv
    return 12


def uv_info(uv):
    """紫外线指数 → (颜色, 晒不晒描述)。"""
    if uv is None:
        return "#64748b", "--"
    if uv <= 2:
        return "#16a34a", "不晒"
    if uv <= 5:
        return "#ca8a04", "有点晒"
    if uv <= 7:
        return "#f97316", "较晒"
    if uv <= 10:
        return "#ef4444", "很晒"
    return "#9333ea", "极晒"


def build_tips(base_tip, desc, temp, wind_kmph, uv):
    """动态组合小贴士：基础搭配提示 + 雨雪/大风/紫外线提醒。"""
    tips = []
    if base_tip:
        tips.append(base_tip)
    if desc:
        if "雨" in desc:
            tips.append("☔ 有雨，出门记得带伞")
        if "雪" in desc:
            tips.append("❄️ 有雪，注意保暖防滑")
    if wind_kmph is not None and wind_kmph >= 20:
        lv = wind_scale(wind_kmph)
        if temp < 24:
            tips.append(f"💨 风力{lv}级较大，体感比气温更低，注意防风")
    if uv is not None and uv >= 6:
        lv_txt = "强" if uv <= 7 else "很强" if uv <= 10 else "极强"
        tips.append(f"☀️ 紫外线{lv_txt}（UV {uv}），出门注意防晒")
    return "\n".join(tips)


def fetch_weather(city):
    """通过 wttr.in 获取天气，返回 dict。"""
    target = urllib.parse.quote(city) if city else ""
    url = f"https://wttr.in/{target}?format=j1"
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
    with urllib.request.urlopen(req, timeout=12) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    c = data["current_condition"][0]
    na = data["nearest_area"][0]

    desc = None
    if c.get("lang_zh"):
        desc = c["lang_zh"][0].get("value")
    if not desc and c.get("weatherDesc"):
        raw = c["weatherDesc"][0].get("value", "").strip()
        desc = WEATHER_ZH.get(raw, raw)

    uv_raw = c.get("uvIndex")
    try:
        uv = int(uv_raw)
    except (TypeError, ValueError):
        uv = None

    try:
        wind_kmph = int(float(c.get("windspeedKmph") or 0))
    except (TypeError, ValueError):
        wind_kmph = None

    return {
        "temp": float(c["temp_C"]),
        "feels": c.get("FeelsLikeC"),
        "humidity": c.get("humidity"),
        "desc": desc,
        "area": na["areaName"][0]["value"],
        "region": na["region"][0]["value"],
        "wind_kmph": wind_kmph,
        "wind_dir": c.get("winddir16Point") or "",
        "uv": uv,
    }


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("穿衣建议")
        self.geometry("470x460")
        self.resizable(False, False)
        self.configure(bg=BG)
        self._build_ui()
        self.after(150, self.query_city)

    # ---------- 基础控件 ----------
    def _card(self, parent, **kw):
        return tk.Frame(parent, bg=CARD, highlightbackground=BORDER,
                        highlightthickness=1, **kw)

    def _btn(self, parent, text, cmd, primary=False, width=6):
        bg = ACCENT if primary else "#eef2f8"
        fg = "white" if primary else "#374151"
        ab = ACCENT_DARK if primary else "#e2e8f0"
        b = tk.Button(parent, text=text, command=cmd, relief="flat", bd=0,
                      bg=bg, fg=fg, activebackground=ab, activeforeground=fg,
                      font=(FONT, 10), width=width, cursor="hand2",
                      pady=3)
        return b

    # ---------- 界面 ----------
    def _build_ui(self):
        # 顶部色带
        header = tk.Frame(self, bg=ACCENT, height=86)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="👔 穿衣建议", font=(FONT, 17, "bold"),
                 bg=ACCENT, fg="white").pack(anchor="w", padx=22, pady=(14, 0))
        tk.Label(header, text="26度穿衣法则 · 气温 + 衣物保暖度 = 26℃",
                 font=(FONT, 9), bg=ACCENT, fg="#dbeafe").pack(anchor="w", padx=22)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=16, pady=14)

        # 查询卡片
        qcard = self._card(body)
        qcard.pack(fill="x")

        r1 = tk.Frame(qcard, bg=CARD)
        r1.pack(fill="x", padx=12, pady=(12, 4))
        tk.Label(r1, text="城市", font=(FONT, 10), bg=CARD, fg=MUTED).pack(side="left")
        self.city_var = tk.StringVar(value=DEFAULT_CITY)
        self.city_entry = tk.Entry(r1, textvariable=self.city_var, width=16,
                                   font=(FONT, 11), relief="solid", bd=1,
                                   highlightthickness=0, fg=TEXT)
        self.city_entry.pack(side="left", padx=8)
        self.query_btn = self._btn(r1, "查询", self.query_city, primary=True)
        self.query_btn.pack(side="left")

        r2 = tk.Frame(qcard, bg=CARD)
        r2.pack(fill="x", padx=12, pady=(2, 12))
        tk.Label(r2, text="气温", font=(FONT, 10), bg=CARD, fg=MUTED).pack(side="left")
        self.temp_var = tk.StringVar()
        self.temp_entry = tk.Entry(r2, textvariable=self.temp_var, width=10,
                                   font=(FONT, 11), relief="solid", bd=1,
                                   highlightthickness=0, fg=TEXT)
        self.temp_entry.pack(side="left", padx=8)
        tk.Label(r2, text="℃", font=(FONT, 11), bg=CARD, fg=MUTED).pack(side="left")
        self._btn(r2, "按气温查", self.query_temp, width=8).pack(side="right")

        # 结果卡片（grid 布局，便于动态显隐环境信息行）
        rcard = self._card(body)
        rcard.pack(fill="both", expand=True, pady=(12, 0))
        rcard.grid_columnconfigure(0, weight=1)
        rcard.grid_rowconfigure(7, weight=1)

        top = tk.Frame(rcard, bg=CARD)
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 0))
        self.loc_label = tk.Label(top, font=(FONT, 10), bg=CARD, fg=MUTED)
        self.loc_label.pack(anchor="w")

        temp_row = tk.Frame(rcard, bg=CARD)
        temp_row.grid(row=1, column=0, sticky="ew", padx=16, pady=(2, 0))
        self.emoji_label = tk.Label(temp_row, font=(FONT, 24), bg=CARD)
        self.emoji_label.pack(side="left")
        self.temp_label = tk.Label(temp_row, font=(FONT, 32, "bold"),
                                   bg=CARD, fg=ACCENT)
        self.temp_label.pack(side="left", padx=(4, 0))
        self.desc_label = tk.Label(temp_row, font=(FONT, 11), bg=CARD, fg=MUTED)
        self.desc_label.pack(side="left", padx=(10, 0), pady=(12, 0))

        # 环境信息行：风力 / 紫外线 / 湿度
        self.env_row = tk.Frame(rcard, bg=CARD)
        self.env_row.grid(row=2, column=0, sticky="ew", padx=16, pady=(6, 0))
        self.wind_chip = tk.Label(self.env_row, text="", bg=CHIP_BG, fg="#475569",
                                  font=(FONT, 9), padx=8, pady=3)
        self.wind_chip.pack(side="left")
        self.sun_chip = tk.Label(self.env_row, text="", bg=CHIP_BG, fg="#475569",
                                 font=(FONT, 9), padx=8, pady=3)
        self.sun_chip.pack(side="left", padx=(6, 0))
        self.hum_chip = tk.Label(self.env_row, text="", bg=CHIP_BG, fg="#475569",
                                 font=(FONT, 9), padx=8, pady=3)
        self.hum_chip.pack(side="left", padx=(6, 0))
        self.env_row.grid_remove()  # 默认隐藏，查询成功才显示

        # 分隔线
        tk.Frame(rcard, bg=BORDER, height=1).grid(row=3, column=0,
                                                  sticky="ew", padx=16, pady=10)

        tk.Label(rcard, text="建议搭配", font=(FONT, 9), bg=CARD,
                 fg=MUTED).grid(row=4, column=0, sticky="w", padx=16)
        self.outfit_label = tk.Label(rcard, font=(FONT, 13, "bold"),
                                     bg=CARD, fg=TEXT, justify="left",
                                     wraplength=420)
        self.outfit_label.grid(row=5, column=0, sticky="w", padx=16, pady=(2, 0))
        self.tip_label = tk.Label(rcard, font=(FONT, 10), bg=CARD,
                                  fg=MUTED, justify="left", wraplength=420)
        self.tip_label.grid(row=6, column=0, sticky="nw", padx=16, pady=(2, 14))

        # 状态栏
        self.status_label = tk.Label(self, text="", font=(FONT, 9), bg=BG,
                                     fg="#a6adba", anchor="w")
        self.status_label.pack(fill="x", padx=18, pady=(0, 8))

    # ---------- 逻辑 ----------
    def _set_status(self, text):
        self.status_label.config(text=text)

    def _set_env(self, w):
        """填充并显示环境信息行。w 为 fetch_weather 返回的 dict。"""
        wind_txt = ""
        if w.get("wind_kmph") is not None:
            lv = wind_scale(w["wind_kmph"])
            dir_zh = WIND_DIR_ZH.get(w.get("wind_dir") or "", "")
            prefix = f"{dir_zh}风" if dir_zh else "风"
            wind_txt = f"💨 {prefix} {lv}级 · {w['wind_kmph']}km/h"
        self.wind_chip.config(text=wind_txt or "💨 风力 --")

        uv = w.get("uv")
        color, txt = uv_info(uv)
        self.sun_chip.config(text=f"☀️ 紫外线 {uv if uv is not None else '--'} · {txt}",
                             fg=color)

        hum = w.get("humidity")
        self.hum_chip.config(text=f"💧 湿度 {hum}%" if hum else "💧 湿度 --")

        self.env_row.grid()

    def query_city(self):
        city = self.city_var.get().strip()
        if not city:
            self._set_status("请输入城市名")
            return
        self.query_btn.config(state="disabled")
        self._set_status(f"正在查询「{city}」…")
        threading.Thread(target=self._fetch_city, args=(city,), daemon=True).start()

    def _fetch_city(self, city):
        try:
            w = fetch_weather(city)
            self.after(0, self._render_weather, city, w)
        except Exception as e:
            self.after(0, self._render_error, f"查询失败：{e}")

    def _render_weather(self, city, w):
        self.query_btn.config(state="normal")
        temp = w["temp"]
        outfit, base_tip = pick_outfit(temp)
        emoji, color = temp_style(temp)

        parts = [city]
        if w.get("feels"):
            parts.append(f"体感 {w['feels']}℃")
        self.loc_label.config(text=" · ".join(parts))

        self.emoji_label.config(text=emoji)
        self.temp_label.config(text=f"{temp:.0f}℃", fg=color)
        self.desc_label.config(text=w.get("desc") or "")
        self.outfit_label.config(text=outfit, fg=TEXT)
        self.tip_label.config(
            text=build_tips(base_tip, w.get("desc"), temp,
                            w.get("wind_kmph"), w.get("uv")))
        self._set_env(w)
        self._set_status("查询成功 · 关闭窗口即可退出")

    def _render_error(self, msg):
        self.query_btn.config(state="normal")
        self.env_row.grid_remove()
        self.outfit_label.config(text=msg, fg="#c0392b")
        self.tip_label.config(text="")
        self._set_status("")

    def query_temp(self):
        s = self.temp_var.get().strip()
        try:
            temp = float(s)
        except ValueError:
            self._set_status("气温请输入数字，如 18")
            return
        outfit, base_tip = pick_outfit(temp)
        emoji, color = temp_style(temp)
        self.loc_label.config(text="手动输入")
        self.emoji_label.config(text=emoji)
        self.temp_label.config(text=f"{temp:.0f}℃", fg=color)
        self.desc_label.config(text="")
        self.outfit_label.config(text=outfit, fg=TEXT)
        self.tip_label.config(text=base_tip if base_tip else "")
        self.env_row.grid_remove()
        self._set_status("已按手动气温给出建议")


if __name__ == "__main__":
    App().mainloop()
