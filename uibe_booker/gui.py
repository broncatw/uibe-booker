"""图形界面：tkinter 版预约助手。

运行：python -m uibe_booker.gui
功能：填学号密码（可保存到本地 config.local.toml，不入库）、
测试登录、查询区域/座位、一键预约、查看我的预约。
所有网络请求在后台线程执行，界面不卡顿。
"""

from __future__ import annotations

import json
import threading
import tkinter as tk
from tkinter import ttk

from uibe_booker.client import ICSeatClient
from uibe_booker.config import DEFAULT_CONFIG_FILE, BookConfig


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("贸大预约助手 · 图书馆座位/研讨间")
        root.geometry("820x620")

        pad = {"padx": 6, "pady": 4}
        frm_top = ttk.LabelFrame(root, text="账号（只保存在本机 config.local.toml）")
        frm_top.pack(fill="x", **pad)

        ttk.Label(frm_top, text="学号").grid(row=0, column=0, **pad)
        self.e_user = ttk.Entry(frm_top, width=22)
        self.e_user.grid(row=0, column=1, **pad)
        ttk.Label(frm_top, text="密码").grid(row=0, column=2, **pad)
        self.e_pass = ttk.Entry(frm_top, width=22, show="*")
        self.e_pass.grid(row=0, column=3, **pad)
        ttk.Button(frm_top, text="保存配置", command=self.save_config).grid(row=0, column=4, **pad)

        ttk.Label(frm_top, text="用户名字段").grid(row=1, column=0, **pad)
        self.e_field = ttk.Entry(frm_top, width=22)
        self.e_field.insert(0, "username")
        self.e_field.grid(row=1, column=1, **pad)
        ttk.Label(frm_top, text="系统地址").grid(row=1, column=2, **pad)
        self.e_base = ttk.Entry(frm_top, width=34)
        self.e_base.insert(0, "http://seat.uibe.edu.cn")
        self.e_base.grid(row=1, column=3, columnspan=2, **pad)

        frm_q = ttk.LabelFrame(root, text="查询与预约")
        frm_q.pack(fill="x", **pad)
        ttk.Label(frm_q, text="日期").grid(row=0, column=0, **pad)
        self.e_day = ttk.Entry(frm_q, width=12)
        self.e_day.grid(row=0, column=1, **pad)
        ttk.Button(frm_q, text="测试登录", command=lambda: self.run(self.do_login)).grid(row=0, column=2, **pad)
        ttk.Button(frm_q, text="区域列表", command=lambda: self.run(self.do_areas)).grid(row=0, column=3, **pad)

        ttk.Label(frm_q, text="空间ID").grid(row=1, column=0, **pad)
        self.e_space = ttk.Entry(frm_q, width=12)
        self.e_space.grid(row=1, column=1, **pad)
        ttk.Button(frm_q, text="查座位", command=lambda: self.run(self.do_seats)).grid(row=1, column=2, **pad)
        ttk.Button(frm_q, text="我的预约", command=lambda: self.run(self.do_mine)).grid(row=1, column=3, **pad)

        ttk.Label(frm_q, text="座位ID").grid(row=2, column=0, **pad)
        self.e_seat = ttk.Entry(frm_q, width=12)
        self.e_seat.grid(row=2, column=1, **pad)
        ttk.Label(frm_q, text="起").grid(row=2, column=2, **pad)
        self.e_start = ttk.Entry(frm_q, width=8)
        self.e_start.insert(0, "18:30")
        self.e_start.grid(row=2, column=3, **pad)
        ttk.Label(frm_q, text="止").grid(row=2, column=4, **pad)
        self.e_end = ttk.Entry(frm_q, width=8)
        self.e_end.insert(0, "22:00")
        self.e_end.grid(row=2, column=5, **pad)
        ttk.Button(frm_q, text="预 约", command=lambda: self.run(self.do_book)).grid(row=2, column=6, **pad)

        frm_log = ttk.LabelFrame(root, text="输出")
        frm_log.pack(fill="both", expand=True, **pad)
        self.txt = tk.Text(frm_log, height=18)
        self.txt.pack(fill="both", expand=True, padx=4, pady=4)

        self.client: ICSeatClient | None = None
        self._load_config()

    # ---------------- 配置 ----------------
    def _config_from_fields(self) -> BookConfig:
        return BookConfig(
            username=self.e_user.get().strip(),
            password=self.e_pass.get(),
            base_url=self.e_base.get().strip() or "http://seat.uibe.edu.cn",
            login_field=self.e_field.get().strip() or "username",
        )

    def _load_config(self):
        try:
            cfg = BookConfig.load()
            self.e_user.delete(0, tk.END); self.e_user.insert(0, cfg.username)
            self.e_pass.delete(0, tk.END); self.e_pass.insert(0, cfg.password)
            self.e_base.delete(0, tk.END); self.e_base.insert(0, cfg.base_url)
            self.e_field.delete(0, tk.END); self.e_field.insert(0, cfg.login_field)
            self.log("已加载本地配置 config.local.toml")
        except Exception:
            self.log("未找到本地配置，请填写学号密码后点「保存配置」")

    def save_config(self):
        cfg = self._config_from_fields()
        lines = [
            f'username = "{cfg.username}"',
            f'password = "{cfg.password}"',
            f'base_url = "{cfg.base_url}"',
            f'auth_header = "{cfg.auth_header}"',
            f'login_field = "{cfg.login_field}"',
        ]
        with open(DEFAULT_CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        self.log(f"配置已保存到 {DEFAULT_CONFIG_FILE}（该文件不会被提交）")

    # ---------------- 通用执行 ----------------
    def log(self, text: str):
        self.txt.insert(tk.END, text + "\n")
        self.txt.see(tk.END)

    def run(self, func):
        """在后台线程执行网络操作，完成后回主线程输出。"""
        def worker():
            try:
                data = func()
                serialized = json.dumps(data, ensure_ascii=False, indent=2, default=str)
                self.root.after(0, lambda: (self.log("→ 成功"), self.log(serialized[:3000])))
            except Exception as exc:                 # noqa: BLE001
                self.root.after(0, lambda: self.log(f"✗ 失败: {exc}"))
        threading.Thread(target=worker, daemon=True).start()

    def _client(self) -> ICSeatClient:
        if self.client is None:
            self.client = ICSeatClient(self._config_from_fields())
        return self.client

    # ---------------- 动作 ----------------
    def do_login(self):
        self.client = None                        # 重新用当前表单配置登录
        token = self._client().login()
        return {"登录成功，令牌前缀": token[:8]}

    def do_areas(self):
        return self._client().buildings()

    def do_seats(self):
        day = self.e_day.get().strip()
        if not day:
            raise ValueError("请先填写日期 YYYY-MM-DD")
        return self._client().seats(self.e_space.get().strip(), day)

    def do_book(self):
        day = self.e_day.get().strip()
        if not day:
            raise ValueError("请先填写日期 YYYY-MM-DD")
        return self._client().reserve(self.e_seat.get().strip(), day,
                                      self.e_start.get().strip(),
                                      self.e_end.get().strip())

    def do_mine(self):
        return self._client().my_reservations()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
