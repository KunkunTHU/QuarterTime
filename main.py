import sqlite3
import tkinter as tk
from datetime import datetime
from tkinter import ttk
from contextlib import contextmanager
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates

# ================= 颜色配置（新增） =================
COLOR_SCHEME = {
    "Work": "#E74C3C",    # 鲜艳红色
    "Chores": "#2ECC71",  # 鲜明绿色
    "Rest/Entertain": "#3498DB",  # 深蓝色
    "Sleep": "#9B59B6"    # 紫色
}

# ================= 数据库管理模块 =================
class TimeTrackerDB:
    def __init__(self, db_name='time_tracker.db'):
        self.db_name = db_name
        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_name)
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS time_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    activity_type TEXT NOT NULL,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS current_status (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    current_activity TEXT,
                    last_start TIMESTAMP
                )
            ''')

    def log_activity(self, activity_type):
        """记录新的活动类型（相同状态不重复记录）"""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with self._get_connection() as conn:
            current = conn.execute(
                "SELECT current_activity FROM current_status WHERE id = 1"
            ).fetchone()

            if current and current[0] == activity_type:
                return False

            if current and current[0]:
                conn.execute(
                    "UPDATE time_records SET end_time = ? WHERE end_time IS NULL",
                    (now,)
                )

            conn.execute(
                "REPLACE INTO current_status (id, current_activity, last_start) VALUES (1, ?, ?)",
                (activity_type, now)
            )
            conn.execute(
                "INSERT INTO time_records (activity_type, start_time) VALUES (?, ?)",
                (activity_type, now)
            )
            conn.commit()
            return True

    def get_today_records(self):
        """获取当日所有记录（修复时间计算）"""
        today_start = datetime.now().replace(hour=0, minute=0, second=0).strftime('%Y-%m-%d %H:%M:%S')
        with self._get_connection() as conn:
            cursor = conn.execute(f'''
                SELECT 
                    activity_type,
                    start_time,
                    COALESCE(end_time, datetime('now')) as end_time,
                    MAX(0, 
                        (strftime('%s', COALESCE(end_time, datetime('now'))) 
                        - strftime('%s', start_time))
                    ) AS duration
                FROM time_records
                WHERE date(start_time) >= date('{today_start}')
                ORDER BY start_time
            ''')
            return cursor.fetchall()

    def get_history(self):
        """获取完整历史记录"""
        with self._get_connection() as conn:
            cursor = conn.execute('''
                SELECT 
                    activity_type,
                    start_time,
                    end_time,
                    MAX(0, 
                        (strftime('%s', COALESCE(end_time, datetime('now'))) 
                        - strftime('%s', start_time))
                    ) AS duration
                FROM time_records
                ORDER BY start_time
            ''')
            return cursor.fetchall()

    def get_current_status(self):
        """获取当前状态"""
        with self._get_connection() as conn:
            current = conn.execute(
                "SELECT current_activity, last_start FROM current_status WHERE id = 1"
            ).fetchone()
            return current if current else (None, None)
        
    def get_date_records(self, target_date):
        """获取指定日期的记录"""
        date_str = target_date.strftime('%Y-%m-%d')
        with self._get_connection() as conn:
            cursor = conn.execute(f'''
                SELECT 
                    activity_type,
                    start_time,
                    COALESCE(end_time, datetime('now')) as end_time,
                    MAX(0, 
                        (strftime('%s', COALESCE(end_time, datetime('now'))) 
                        - strftime('%s', start_time))
                    ) AS duration
                FROM time_records
                WHERE date(start_time) = date('{date_str}')
                ORDER BY start_time
            ''')
            return cursor.fetchall()

# ================= GUI界面模块 =================
class TimeTrackerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("时间跟踪器")
        self.geometry("500x400")
        
        # 初始化样式系统（新增关键修复）
        self.style = ttk.Style()
        self._init_styles()  # 新增样式初始化方法
        
        self.db = TimeTrackerDB()
        self._create_widgets()
        self._update_status_display()

    def _init_styles(self):
        """初始化所有控件样式"""
        # 圆角按钮样式（修复配置方式）
        self.style.configure('Rounded.TButton', 
                           borderwidth=0,
                           relief="flat",
                           padding=10,
                           font=('微软雅黑', 12, 'bold'),
                           foreground="white",
                           width=12)
        
        # 由于ttk原生不支持borderradius，改用tkinter按钮（调整方案）
        self.option_add('*TButton*highlightThickness', 0)
        self.option_add('*TButton*borderWidth', 0)

    def _create_widgets(self):
        # 状态显示
        self.status_var = tk.StringVar()
        status_frame = ttk.Frame(self)
        ttk.Label(status_frame, 
                 textvariable=self.status_var, 
                 font=('微软雅黑', 12, 'bold'),
                 foreground="#333333").pack(pady=15)
        status_frame.pack(fill='x')

        # 按钮区域（修改布局和样式）
        btn_frame = ttk.Frame(self)
        buttons = [
            ("Work", 0, 0),
            ("Chores", 0, 1),
            ("Rest/Entertain", 1, 0),
            ("Sleep", 1, 1)
        ]

        # 统一按钮样式
        self.style.configure('Rounded.TButton', 
                           borderwidth=0,
                           relief="flat",
                           padding=10,
                           font=('微软雅黑', 12, 'bold'),
                           foreground="white",
                           width=12,
                           borderradius=15)

        # 在按钮创建代码中修改配置方式
        for text, row, col in buttons:
            btn = tk.Button(
                btn_frame,
                text=text,
                command=lambda t=text: self._handle_button_click(t),
                bg=COLOR_SCHEME[text],  # 正确参数名称为bg
                activebackground=COLOR_SCHEME[text],
                fg="white",
                font=('微软雅黑', 12, 'bold'),
                relief="flat",
                padx=20,
                pady=10,
                borderwidth=0,
                highlightthickness=0,
            )
            # 删除原来的btn.configure语句
            btn.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            btn_frame.grid_rowconfigure(row, weight=1, uniform="btns")
            btn_frame.grid_columnconfigure(col, weight=1, uniform="btns")

        btn_frame.pack(pady=20, padx=20, fill='both', expand=True)

        # 功能按钮区域
        control_frame = ttk.Frame(self)
        ttk.Button(
            control_frame,
            text="历史记录",
            command=self.show_history,
            style="TButton"
        ).pack(side=tk.LEFT, padx=10)
        
        ttk.Button(
            control_frame,
            text="数据分析",
            command=self.show_analysis,
            style="TButton"
        ).pack(side=tk.LEFT, padx=10)
        
        control_frame.pack(pady=10)

    def _handle_button_click(self, activity_type):
        """处理按钮点击事件"""
        if self.db.log_activity(activity_type):
            self._update_status_display()

    def _update_status_display(self):
        """更新状态显示"""
        activity, start_time = self.db.get_current_status()
        if activity:
            display_time = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S').strftime('%H:%M:%S')
            self.status_var.set(f"当前状态：{activity}\n开始时间：{display_time}")
        else:
            self.status_var.set("当前状态：未开始")

    def show_history(self):
        """显示完整历史记录"""
        records = self.db.get_history()
        
        history_window = tk.Toplevel(self)
        history_window.title("历史记录")
        history_window.geometry("800x400")
        
        tree = ttk.Treeview(
            history_window,
            columns=('activity', 'start', 'end', 'duration'),
            show='headings'
        )
        
        tree.heading('activity', text='活动类型')
        tree.heading('start', text='开始时间')
        tree.heading('end', text='结束时间')
        tree.heading('duration', text='持续时间（秒）')
        
        tree.column('activity', width=120, anchor='center')
        tree.column('start', width=150, anchor='center')
        tree.column('end', width=150, anchor='center')
        tree.column('duration', width=100, anchor='center')
        
        for record in records:
            end_time = record[2] if record[2] else "进行中"
            duration = f"{record[3]}秒" if record[3] >=0 else "计算错误"
            tree.insert('', 'end', values=(
                record[0],
                record[1],
                end_time,
                duration
            ))
        
        scrollbar = ttk.Scrollbar(history_window, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def show_analysis(self):
        """显示带日期选择的分析窗口"""
        analysis_window = tk.Toplevel(self)
        analysis_window.title("数据分析")
        analysis_window.geometry("1200x800")

        # 日期选择区域
        control_frame = ttk.Frame(analysis_window)
        
        self.selected_date = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        
        ttk.Label(control_frame, text="选择日期:").pack(side=tk.LEFT, padx=5)
        date_entry = ttk.Entry(control_frame, textvariable=self.selected_date, width=12)
        date_entry.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            control_frame,
            text="应用",
            command=self._refresh_analysis
        ).pack(side=tk.LEFT, padx=10)
        
        control_frame.pack(pady=10)

        # 创建Notebook容器
        self.analysis_notebook = ttk.Notebook(analysis_window)
        self._refresh_analysis()
        self.analysis_notebook.pack(expand=True, fill='both')

    def _refresh_analysis(self):
        """刷新分析内容"""
        # 销毁旧内容
        for child in self.analysis_notebook.winfo_children():
            child.destroy()

        # 获取选定日期
        try:
            selected_date = datetime.strptime(self.selected_date.get(), '%Y-%m-%d')
        except ValueError:
            tk.messagebox.showerror("错误", "日期格式无效，请使用YYYY-MM-DD格式")
            return

        # 获取数据
        records = self.db.get_date_records(selected_date)
        valid_records = [r for r in records if r[3] > 0]
        
        if not valid_records:
            tk.messagebox.showinfo("提示", "选定日期没有有效数据")
            return

        # 创建新内容
        timeline_frame = ttk.Frame(self.analysis_notebook)
        self._create_timeline_chart(timeline_frame, valid_records, selected_date)
        self.analysis_notebook.add(timeline_frame, text="时间线")
        
        stats_frame = ttk.Frame(self.analysis_notebook)
        self._create_stat_charts(stats_frame, valid_records)
        self.analysis_notebook.add(stats_frame, text="统计")

    def _create_timeline_chart(self, parent, records, selected_date):
        """创建分段时间线图表（修复未来时间问题）"""
        fig = plt.Figure(figsize=(10, 8), dpi=100)
        time_slots = [
            ("00:00-06:00", 0, 6),
            ("06:00-12:00", 6, 12),
            ("12:00-18:00", 12, 18),
            ("18:00-24:00", 18, 23)
        ]
        
        now = datetime.now()
        target_date = selected_date.date() if selected_date else now.date()
        is_today = (now.date() == target_date)
        
        axes = fig.subplots(4, 1, gridspec_kw={'height_ratios': [1,1,1,1]})
        
        for idx, (title, start_hour, end_hour) in enumerate(time_slots):
            ax = axes[idx]
            ax.set_title(f"Time Slot: {title}")
            
            # 设置完整时间段
            slot_start = datetime(target_date.year, target_date.month, target_date.day, start_hour)
            slot_end = datetime(target_date.year, target_date.month, target_date.day, end_hour)
            
            # 处理最后一个时间段
            if end_hour == 23:
                slot_end = slot_end.replace(hour=23, minute=59, second=59)
            
            # 当日时间处理
            if is_today:
                current_time = datetime.now()
                # 自动调整结束时间为当前时间（如果时间段尚未结束）
                if slot_end > current_time:
                    slot_end = current_time
            
            # 绘制时间段背景
            ax.axhspan(ymin=-1, ymax=1, xmin=0, xmax=1, color='#F5F5F5', alpha=0.3)
            
            # 绘制有效记录
            for record in records:
                start = datetime.strptime(record[1], '%Y-%m-%d %H:%M:%S')
                end = datetime.strptime(record[2], '%Y-%m-%d %H:%M:%S') if record[2] else now
                
                # 过滤非当前时间段记录
                if start > slot_end or end < slot_start:
                    continue
                
                # 计算实际绘制范围
                draw_start = max(start, slot_start)
                draw_end = min(end, slot_end)
                
                # 确保不绘制未来时间
                if is_today:
                    draw_end = min(draw_end, now)
                
                duration = (draw_end - draw_start).total_seconds() / 3600
                if duration > 0:
                    ax.barh(
                        y=0, 
                        width=duration, 
                        left=draw_start,
                        height=0.5,
                        color=COLOR_SCHEME[record[0]],
                        edgecolor='white'
                    )

            # 设置坐标轴格式
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax.set_xlim(slot_start.replace(hour=start_hour), slot_end)
            ax.yaxis.set_visible(False)
            ax.grid(axis='x', alpha=0.3)

        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _create_stat_charts(self, parent, records):
        """创建统计图表（增加数据校验）"""
        fig = plt.Figure(figsize=(10, 8), dpi=100)
        
        # 计算总时长
        durations = {}
        for record in records:
            if record[3] > 0:
                durations[record[0]] = durations.get(record[0], 0) + record[3]
        
        # 过滤无效数据
        activities = [k for k, v in durations.items() if v > 0]
        times = [durations[k] / 3600 for k in activities]  # 转换为小时
        
        if not activities:
            tk.messagebox.showinfo("提示", "没有有效数据可供展示")
            return

        color_mapping = {
            "Work": "#FF6B6B",
            "Chores": "#4ECDC4",
            "Rest/Entertain": "#45B7D1",
            "Sleep": "#96CEB4"
        }
        used_colors = [color_mapping[act] for act in activities]

        # 柱状图
        ax1 = fig.add_subplot(211)
        ax1.bar(activities, times, color=used_colors)
        # 在 _create_stat_charts 方法中
        ax1.set_ylabel("Hours")                  # Y轴标签改为英文
        ax1.set_title("Total Duration by Activity")  # 标题改为英文

        # 饼图
        ax2 = fig.add_subplot(212)
        total = sum(times)
        ax2.pie(times, labels=activities, colors=used_colors,
               autopct=lambda p: f'{p:.1f}%\n({p*total/100:.1f}h)',
               startangle=90)
        ax2.set_title("Time Distribution")

        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

# ================= 主程序入口 =================
if __name__ == "__main__":
    app = TimeTrackerApp()
    app.mainloop()