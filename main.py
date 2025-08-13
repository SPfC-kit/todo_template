import json
import os
from dataclasses import dataclass, asdict, field
from datetime import datetime, date
from typing import Optional, List

import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import font as tkfont

DATA_FILE = "todo_data.json"


@dataclass
class Task:
    id: int
    text: str
    due: Optional[str] = None  # "YYYY-MM-DD" or None
    completed: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    @staticmethod
    def from_dict(d: dict) -> "Task":
        return Task(
            id=int(d["id"]),
            text=str(d["text"]),
            due=d.get("due") or None,
            completed=bool(d.get("completed", False)),
            created_at=str(d.get("created_at", datetime.now().isoformat(timespec="seconds"))),
        )

    def to_dict(self) -> dict:
        return asdict(self)


def parse_date_safe(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


class TodoApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("ToDo - Python標準だけで動く")
        self.root.geometry("700x450")
        self.root.minsize(640, 420)

        self.tasks: List[Task] = []
        self.filter_state = tk.StringVar(value="all")  # "all" | "active" | "done"

        # フォントとスタイル
        self.base_font = tkfont.nametofont("TkDefaultFont").copy()
        self.done_font = self.base_font.copy()
        try:
            self.done_font.configure(slant="italic", overstrike=1)
        except tk.TclError:
            # 環境によってoverstrike未対応のことがある
            self.done_font.configure(slant="italic")

        style = ttk.Style(self.root)
        # Windows等で見た目を少し整える
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Treeview", rowheight=26)

        self._build_ui()

        self.load()
        self.refresh_tree()

    # ---------------- UI ----------------
    def _build_ui(self):
        # 上段: 入力行
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill="x")

        ttk.Label(top, text="タスク").grid(row=0, column=0, sticky="w")
        self.task_var = tk.StringVar()
        self.task_entry = ttk.Entry(top, textvariable=self.task_var)
        self.task_entry.grid(row=1, column=0, sticky="we", padx=(0, 8))
        self.task_entry.bind("<Return>", lambda e: self.add_task())

        ttk.Label(top, text="期限 (YYYY-MM-DD, 任意)").grid(row=0, column=1, sticky="w")
        self.due_var = tk.StringVar()
        self.due_entry = ttk.Entry(top, textvariable=self.due_var, width=18)
        self.due_entry.grid(row=1, column=1, sticky="w", padx=(0, 8))

        self.add_btn = ttk.Button(top, text="追加 (Enter)", command=self.add_task)
        self.add_btn.grid(row=1, column=2, sticky="w")

        top.columnconfigure(0, weight=1)

        # 中段: フィルタ + リスト
        mid = ttk.Frame(self.root, padding=(8, 0, 8, 8))
        mid.pack(fill="both", expand=True)

        filters = ttk.Frame(mid)
        filters.pack(fill="x", pady=(0, 4))
        ttk.Label(filters, text="表示:").pack(side="left")
        for val, label in [("all", "すべて"), ("active", "未完了"), ("done", "完了")]:
            ttk.Radiobutton(filters, text=label, value=val, variable=self.filter_state,
                            command=self.refresh_tree).pack(side="left", padx=4)

        # Treeview（一覧）
        columns = ("text", "due", "status")
        self.tree = ttk.Treeview(mid, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("text", text="タスク")
        self.tree.heading("due", text="期限")
        self.tree.heading("status", text="状態")
        self.tree.column("text", width=420, anchor="w")
        self.tree.column("due", width=120, anchor="center")
        self.tree.column("status", width=80, anchor="center")

        # 完了タスクの見た目
        self.tree.tag_configure("done", foreground="#888888", font=self.done_font)

        self.tree.bind("<Double-1>", lambda e: self.edit_task())
        self.tree.bind("<Delete>", lambda e: self.delete_task())
        self.tree.pack(fill="both", expand=True)

        # 下段: 操作ボタン + ステータス
        bottom = ttk.Frame(self.root, padding=8)
        bottom.pack(fill="x")

        ttk.Button(bottom, text="編集 (ダブルクリック)", command=self.edit_task).pack(side="left")
        ttk.Button(bottom, text="完了 切替 (Ctrl+D)", command=self.toggle_complete).pack(side="left", padx=6)
        ttk.Button(bottom, text="削除 (Delete)", command=self.delete_task).pack(side="left")

        self.status_var = tk.StringVar()
        ttk.Label(bottom, textvariable=self.status_var, anchor="e").pack(side="right", fill="x", expand=True)

        # ショートカット
        self.root.bind("<Control-d>", lambda e: self.toggle_complete())
        self.root.bind("<Control-s>", lambda e: self.save())

    # ------------- データ処理 -------------
    def next_id(self) -> int:
        return (max((t.id for t in self.tasks), default=0) + 1)

    def add_task(self):
        text = self.task_var.get().strip()
        due_raw = self.due_var.get().strip()
        if not text:
            messagebox.showwarning("入力エラー", "タスク内容を入力してください。")
            return
        if due_raw and not parse_date_safe(due_raw):
            messagebox.showwarning("入力エラー", "期限は YYYY-MM-DD 形式で入力してください。")
            return

        task = Task(id=self.next_id(), text=text, due=due_raw or None)
        self.tasks.append(task)
        self.task_var.set("")
        self.due_var.set("")
        self.save()
        self.refresh_tree()

    def selected_task(self) -> Optional[Task]:
        sel = self.tree.selection()
        if not sel:
            return None
        tid = int(sel[0])
        for t in self.tasks:
            if t.id == tid:
                return t
        return None

    def edit_task(self):
        task = self.selected_task()
        if not task:
            messagebox.showinfo("編集", "編集するタスクを選択してください。")
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("タスクを編集")
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.resizable(False, False)
        ttk.Label(dlg, text="タスク").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 0))
        text_var = tk.StringVar(value=task.text)
        ttk.Entry(dlg, textvariable=text_var, width=48).grid(row=1, column=0, columnspan=2, sticky="we", padx=10)

        ttk.Label(dlg, text="期限 (YYYY-MM-DD, 任意)").grid(row=2, column=0, sticky="w", padx=10, pady=(10, 0))
        due_var = tk.StringVar(value=task.due or "")
        ttk.Entry(dlg, textvariable=due_var, width=20).grid(row=3, column=0, sticky="w", padx=10)

        btns = ttk.Frame(dlg)
        btns.grid(row=4, column=0, columnspan=2, sticky="e", padx=10, pady=10)
        ttk.Button(btns, text="キャンセル", command=dlg.destroy).pack(side="right", padx=(6, 0))

        def on_ok():
            new_text = text_var.get().strip()
            new_due = due_var.get().strip()
            if not new_text:
                messagebox.showwarning("入力エラー", "タスク内容を入力してください。", parent=dlg)
                return
            if new_due and not parse_date_safe(new_due):
                messagebox.showwarning("入力エラー", "期限は YYYY-MM-DD 形式で入力してください。", parent=dlg)
                return
            task.text = new_text
            task.due = new_due or None
            self.save()
            self.refresh_tree()
            dlg.destroy()

        ttk.Button(btns, text="保存", command=on_ok).pack(side="right")

        dlg.bind("<Return>", lambda e: on_ok())
        dlg.bind("<Escape>", lambda e: dlg.destroy())

        # 画面中央に配置
        dlg.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dlg.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry(f"+{max(0, x)}+{max(0, y)}")

    def toggle_complete(self):
        task = self.selected_task()
        if not task:
            messagebox.showinfo("完了切替", "対象のタスクを選択してください。")
            return
        task.completed = not task.completed
        self.save()
        self.refresh_tree()

    def delete_task(self):
        task = self.selected_task()
        if not task:
            messagebox.showinfo("削除", "削除するタスクを選択してください。")
            return
        if not messagebox.askyesno("確認", f"「{task.text}」を削除しますか？"):
            return
        self.tasks = [t for t in self.tasks if t.id != task.id]
        self.save()
        self.refresh_tree()

    def refresh_tree(self):
        # クリア
        for iid in self.tree.get_children():
            self.tree.delete(iid)

        # フィルタ
        if self.filter_state.get() == "active":
            view = [t for t in self.tasks if not t.completed]
        elif self.filter_state.get() == "done":
            view = [t for t in self.tasks if t.completed]
        else:
            view = list(self.tasks)

        # ソート: 未完了→完了, 期限(近い順, 未設定は末尾), 作成日時
        def sort_key(t: Task):
            d = parse_date_safe(t.due) or date(9999, 12, 31)
            return (t.completed, d, t.created_at)

        view.sort(key=sort_key)

        # 挿入
        for t in view:
            status = "完了" if t.completed else "未完了"
            due_display = t.due or ""
            tags = ("done",) if t.completed else ()
            self.tree.insert("", "end", iid=str(t.id),
                             values=(t.text, due_display, status),
                             tags=tags)

        # ステータスバー
        total = len(self.tasks)
        remain = len([t for t in self.tasks if not t.completed])
        self.status_var.set(f"全{total}件 / 未完了 {remain}件")

    # ------------- 保存/読込 -------------
    def save(self, silent: bool = True):
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump([t.to_dict() for t in self.tasks], f, ensure_ascii=False, indent=2)
            if not silent:
                messagebox.showinfo("保存", "保存しました。")
        except OSError as e:
            messagebox.showerror("保存エラー", f"保存に失敗しました: {e}")

    def load(self):
        if not os.path.exists(DATA_FILE):
            self.tasks = []
            return
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.tasks = [Task.from_dict(d) for d in data]
        except (OSError, json.JSONDecodeError) as e:
            messagebox.showwarning("読込エラー", f"保存データを読み込めませんでした: {e}\n新規で開始します。")
            self.tasks = []


def main():
    root = tk.Tk()
    app = TodoApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()