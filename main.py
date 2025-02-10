import sqlite3
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk, messagebox
from contextlib import contextmanager
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates

# ================= 颜色配置（新增） =================
# 【NOTICE】在这里调制你喜欢的配色~
COLOR_SCHEME = {
    "Work": "#E74C3C",    # 鲜艳红色
    "Chores": "#F39C12",  # 橙黄色
    "Rest/Entertain": "#3498DB",  # 深蓝色
    "Sleep": "#2ECC71",    # 鲜明绿色
    
    # 新增小按钮颜色
    "Study": "#9B59B6",    # 紫色
    "Exercise": "#1ABC9C",  # 蓝绿色
    "Meeting": "#E67E22",  # 橙色
    "Commute": "#95A5A6"   # 灰色
}

# ================= 数据库管理模块 =================
class TimeTrackerDB:
    def __init__(self, db_name='time_tracker.db'):
        self.db_name = db_name
        self._init_db()
        self._init_cover_table()
    
    def _init_cover_table(self):
        with self._get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS covered_days (
                    day DATE PRIMARY KEY,
                    cover_type TEXT DEFAULT 'gradient'
                )
            ''')
            
    def cover_day(self, day):
        """标记覆盖日期"""
        with self._get_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO covered_days (day) 
                VALUES (?)
            ''', (day.strftime('%Y-%m-%d'),))
            conn.commit()
    
    def get_covered_days(self, year, month):
        """获取指定月份的覆盖日期"""
        with self._get_connection() as conn:
            cursor = conn.execute('''
                SELECT day 
                FROM covered_days
                WHERE strftime('%Y', day) = ? 
                  AND strftime('%m', day) = ?
            ''', (str(year), f"{month:02d}"))
            return [datetime.strptime(row[0], '%Y-%m-%d').date() for row in cursor.fetchall()]

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
        
    # 修改数据库查询方法（关键修改）
    def get_date_records(self, target_date):
        """获取指定日期及跨日未结束的记录（修正当日开始时间）"""
        date_str = target_date.strftime('%Y-%m-%d')
        start_of_day = datetime(target_date.year, target_date.month, target_date.day)
        
        with self._get_connection() as conn:
            cursor = conn.execute(f'''
                SELECT 
                    activity_type,
                    -- 调整开始时间为当日0点（如果跨日）
                    CASE 
                        WHEN start_time < '{start_of_day}' THEN '{start_of_day}' 
                        ELSE start_time 
                    END as adjusted_start,
                    COALESCE(end_time, datetime('now')) as end_time,
                    -- 重新计算持续时间（仅当日部分）
                    MAX(0, 
                        strftime('%s', COALESCE(end_time, datetime('now'))) 
                        - strftime('%s', 
                            CASE 
                                WHEN start_time < '{start_of_day}' THEN '{start_of_day}' 
                                ELSE start_time 
                            END
                        )
                    ) AS duration
                FROM time_records
                WHERE 
                    (
                        date(start_time) = date('{date_str}') 
                        OR 
                        (
                            start_time < '{start_of_day}' 
                            AND 
                            (end_time >= '{start_of_day}' OR end_time IS NULL)
                        )
                    )
                ORDER BY start_time
            ''')
            return cursor.fetchall()
        
    def get_month_records(self, year, month):
        """获取指定月份所有日期的记录（处理跨日记录）"""
        start_date = datetime(year, month, 1)
        next_month = month + 1 if month < 12 else 1
        next_year = year if month < 12 else year + 1
        end_date = datetime(next_year, next_month, 1) - timedelta(days=1)
        
        with self._get_connection() as conn:
            cursor = conn.execute(f'''
                SELECT 
                    activity_type,
                    start_time,
                    COALESCE(end_time, datetime('now')) as end_time
                FROM time_records
                WHERE 
                    start_time <= '{end_date}' 
                    AND 
                    (end_time >= '{start_date}' OR end_time IS NULL)
            ''')
            return cursor.fetchall()
        
    def _clear_history(self):
        """清空历史记录"""
        if tk.messagebox.askyesno("确认", "确定要清空所有历史记录吗？"):
            with self._get_connection() as conn:
                conn.execute("DELETE FROM time_records")
                conn.execute("DELETE FROM current_status")
                conn.commit()
            tk.messagebox.showinfo("提示", "历史记录已清空")
            
    def manual_insert_activity(self, activity_type, start_time):
        """手动插入活动记录并调整相邻记录"""
        start_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
        
        with self._get_connection() as conn:
            # 查找需要分割的原记录
            original = conn.execute('''
                SELECT id, start_time, end_time 
                FROM time_records 
                WHERE start_time <= ? 
                  AND (end_time >= ? OR end_time IS NULL)
                ORDER BY start_time DESC
                LIMIT 1
            ''', (start_str, start_str)).fetchone()
            
            if original:
                orig_id, orig_start, orig_end = original
                # 更新原记录结束时间
                conn.execute('''
                    UPDATE time_records 
                    SET end_time = ? 
                    WHERE id = ?
                ''', (start_str, orig_id))
                
                # 插入新记录
                new_end = orig_end if orig_end else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                conn.execute('''
                    INSERT INTO time_records 
                        (activity_type, start_time, end_time)
                    VALUES (?, ?, ?)
                ''', (activity_type, start_str, new_end))
                
                # 处理后续记录
                if orig_end:
                    conn.execute('''
                        UPDATE time_records 
                        SET start_time = ? 
                        WHERE start_time = ? AND id != last_insert_rowid()
                    ''', (new_end, orig_end))
                
            else:  # 没有重叠记录的情况
                # 查找下一个记录
                next_record = conn.execute('''
                    SELECT MIN(start_time) 
                    FROM time_records 
                    WHERE start_time > ?
                ''', (start_str,)).fetchone()[0]
                
                end_time = next_record if next_record else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                conn.execute('''
                    INSERT INTO time_records 
                        (activity_type, start_time, end_time)
                    VALUES (?, ?, ?)
                ''', (activity_type, start_str, end_time))
            
            conn.commit()
    
    
# ================= GUI界面模块 =================
class TimeTrackerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("QuarterTime")
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

        # ================= 修改按钮区域 =================
        # 创建主按钮容器
        main_btn_frame = ttk.Frame(self)
        
        # 原始4个大按钮（2x2网格）
        big_buttons = [
            ("Work", 0, 0),
            ("Chores", 0, 1),
            ("Rest/Entertain", 1, 0),
            ("Sleep", 1, 1)
        ]

        # 新增4个小按钮（1x4网格）
        small_buttons = [
            ("Study", 0, 0),
            ("Exercise", 0, 1),
            ("Meeting", 0, 2),
            ("Commute", 0, 3)
        ]

        # 创建大按钮区域
        big_btn_frame = ttk.Frame(main_btn_frame)
        for text, row, col in big_buttons:
            btn = tk.Button(
                big_btn_frame,
                text=text,
                command=lambda t=text: self._handle_button_click(t),
                bg=COLOR_SCHEME.get(text, "#CCCCCC"),  # 使用默认颜色
                activebackground=COLOR_SCHEME.get(text, "#CCCCCC"),
                fg="white",
                font=('微软雅黑', 12, 'bold'),
                relief="flat",
                padx=15,
                pady=8,
                borderwidth=0,
                highlightthickness=0,
            )
            btn.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
            big_btn_frame.grid_rowconfigure(row, weight=1, uniform="big_btns")
            big_btn_frame.grid_columnconfigure(col, weight=1, uniform="big_btns")
        big_btn_frame.pack(pady=(0, 10), fill='both', expand=True)

        # 创建小按钮区域
        small_btn_frame = ttk.Frame(main_btn_frame)
        for text, row, col in small_buttons:
            btn = tk.Button(
                small_btn_frame,
                text=text,
                command=lambda t=text: self._handle_button_click(t),
                bg=COLOR_SCHEME.get(text, "#666666"),  # 小按钮使用不同颜色
                activebackground=COLOR_SCHEME.get(text, "#666666"),
                fg="white",
                font=('微软雅黑', 10),  # 更小字号
                relief="flat",
                padx=8,
                pady=4,
                borderwidth=0,
                highlightthickness=0,
            )
            btn.grid(row=row, column=col, padx=4, pady=2, sticky="nsew")
            small_btn_frame.grid_columnconfigure(col, weight=1, uniform="small_btns")
        small_btn_frame.pack(fill='both', expand=True)

        main_btn_frame.pack(pady=20, padx=20, fill='both', expand=True)

        # ================= 功能按钮区域（保持不变） =================
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
            duration = f"{record[3]}秒" if record[3] >= 0 else "计算错误"
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

        # 添加清空记录按钮
        clear_button = ttk.Button(
            history_window,
            text="清空记录",
            command=self.db._clear_history
        )
        clear_button.pack(pady=10)
        
        # 添加操作按钮区域
        button_frame = ttk.Frame(history_window)
        
        ttk.Button(
            button_frame,
            text="手动添加记录",
            command=self._show_manual_add_dialog
        ).pack(side=tk.LEFT, padx=5)
        
        button_frame.pack(pady=10)
        
    def _show_manual_add_dialog(self):
        """显示手动添加记录对话框"""
        dialog = tk.Toplevel(self)
        dialog.title("手动添加记录")
        dialog.geometry("420x160")
        
        # 活动类型选择
        ttk.Label(dialog, text="活动类型:").grid(row=0, column=0, padx=10, pady=10)
        activity_var = tk.StringVar()
        activity_combo = ttk.Combobox(
            dialog,
            textvariable=activity_var,
            values=list(COLOR_SCHEME.keys()),
            state="readonly"
        )
        activity_combo.grid(row=0, column=1, padx=10, pady=10)
        
        # 开始时间输入
        ttk.Label(dialog, text="开始时间 (YYYY-MM-DD HH:MM:SS):").grid(row=1, column=0, padx=10, pady=10)
        start_entry = ttk.Entry(dialog)
        start_entry.grid(row=1, column=1, padx=10, pady=10)
        
        # 状态提示
        status_label = ttk.Label(dialog, text="")
        status_label.grid(row=2, columnspan=2)
        
        def validate_and_submit():
            activity = activity_var.get()
            start_str = start_entry.get()
            
            if not activity:
                status_label.config(text="请选择活动类型", foreground="red")
                return
                
            try:
                start_time = datetime.strptime(start_str, '%Y-%m-%d %H:%M:%S')
                if start_time > datetime.now():
                    raise ValueError("不能添加未来时间的记录")
                    
                # 执行数据库操作
                self.db.manual_insert_activity(activity, start_time)
                # 刷新历史记录窗口
                self.show_history()
                dialog.destroy()
                
            except ValueError as e:
                status_label.config(text=f"输入错误：{str(e)}", foreground="red")
        
        ttk.Button(
            dialog,
            text="提交",
            command=validate_and_submit
        ).grid(row=3, columnspan=2, pady=10)

    def show_analysis(self):
        """显示带日期选择的分析窗口（新增月视图选项卡）"""
        analysis_window = tk.Toplevel(self)
        analysis_window.title("数据分析")
        analysis_window.geometry("1400x800")

        # 日期选择区域（新增年月选择）
        control_frame = ttk.Frame(analysis_window)
        
        # 日视图日期选择
        day_control_frame = ttk.Frame(control_frame)
        self.selected_date = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Label(day_control_frame, text="选择日期:").pack(side=tk.LEFT, padx=5)
        date_entry = ttk.Entry(day_control_frame, textvariable=self.selected_date, width=12)
        date_entry.pack(side=tk.LEFT, padx=5)
        day_control_frame.pack(side=tk.LEFT, padx=10)
        
        # 月视图年月选择
        month_control_frame = ttk.Frame(control_frame)
        self.selected_year = tk.IntVar(value=datetime.now().year)
        self.selected_month = tk.IntVar(value=datetime.now().month)
        
        ttk.Label(month_control_frame, text="选择年份:").pack(side=tk.LEFT)
        year_combo = ttk.Combobox(
            month_control_frame, 
            textvariable=self.selected_year,
            values=list(range(2020, 2031)),
            width=5
        )
        year_combo.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(month_control_frame, text="月份:").pack(side=tk.LEFT)
        month_combo = ttk.Combobox(
            month_control_frame,
            textvariable=self.selected_month,
            values=list(range(1, 13)),
            width=3
        )
        month_combo.pack(side=tk.LEFT, padx=5)
        month_control_frame.pack(side=tk.LEFT, padx=10)
        
        # 应用按钮
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
        
        # 新增月视图内容
        month_frame = ttk.Frame(self.analysis_notebook)
        self._create_month_chart(month_frame)
        self.analysis_notebook.add(month_frame, text="月视图")

    def _create_timeline_chart(self, parent, records, selected_date):
        """创建分段时间线图表（修复刻度标签问题）"""
        fig = plt.Figure(figsize=(10, 8), dpi=100)
        time_slots = [
            ("00:00-06:00", 0, 6),
            ("06:00-12:00", 6, 12),
            ("12:00-18:00", 12, 18),
            ("18:00-24:00", 18, 23)
        ]
        
        color_map = COLOR_SCHEME
        target_date = selected_date.date()
        
        axes = fig.subplots(4, 1, gridspec_kw={'height_ratios': [1,1,1,1]})
        
        for idx, (title, start_hour, end_hour) in enumerate(time_slots):
            ax = axes[idx]
            ax.set_title(f"Time Quarter: {title}")
            
            # 固定时间段设置
            slot_start = datetime(target_date.year, target_date.month, target_date.day, start_hour)
            slot_end = datetime(target_date.year, target_date.month, target_date.day, end_hour)
            
            # 处理最后一个时间段
            if title == "18:00-24:00":
                slot_end = slot_end.replace(hour=23, minute=59, second=59)
                
            # 绘制时间段背景
            ax.axhspan(ymin=-1, ymax=1, xmin=0, xmax=1, color='#F5F5F5', alpha=0.3)
            
            # 绘制有效记录
            for record in records:
                # 使用调整后的开始时间（已在前端处理）
                start = datetime.strptime(record[1], '%Y-%m-%d %H:%M:%S')
                end = datetime.strptime(record[2], '%Y-%m-%d %H:%M:%S') if record[2] else datetime.now()
                
                # 截取在时间段内的有效部分
                draw_start = max(start, slot_start)
                draw_end = min(end, slot_end)
                
                # 跳过不在当前时间段的记录
                if draw_start >= draw_end:
                    continue
                    
                duration_hours = (draw_end - draw_start).total_seconds() / 3600
                
                # 计算相对位置（强制从时间段起点开始）
                left_position = (draw_start - slot_start).total_seconds() / 3600
                if left_position < 0:
                    left_position = 0
                    duration_hours = (draw_end - slot_start).total_seconds() / 3600

                ax.barh(
                    y=0,
                    width=duration_hours,
                    left=left_position,
                    height=2*0.618,
                    color=color_map[record[0]],
                    edgecolor='white'
                )
        
            # 修复刻度标签问题（关键修改）
            if end_hour == 23:
                hours_in_slot = end_hour - start_hour+1
            else:
                hours_in_slot = end_hour - start_hour
            ax.set_xlim(0, hours_in_slot)  # 根据实际时间段设置范围
            ax.set_xticks([x * 0.5 for x in range(0, 2 * hours_in_slot + 1)])  # 包含起始和结束刻度
            
            # 生成正确的刻度标签
            time_labels = [
                f"{(start_hour + x // 2) % 24:02d}:{(x % 2) * 30:02d}" 
                for x in range(0, 2 * hours_in_slot + 1)
            ]
            ax.set_xticklabels(time_labels)
            
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

        used_colors = [COLOR_SCHEME[act] for act in activities]

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
        
    def _create_month_chart(self, parent):
        """创建月视图堆叠条形图（优化版）"""
        year = self.selected_year.get()
        month = self.selected_month.get()
        records = self.db.get_month_records(year, month)
        covered_days = self.db.get_covered_days(year, month)
        
        # 创建自定义渐变色
        from matplotlib.colors import LinearSegmentedColormap
        pink_blue = LinearSegmentedColormap.from_list(
            'pink_blue', ['#FFB6C1', '#87CEFA'], N=256)
        
        # 处理原始数据
        activity_order = [
            'Work', 'Study', 'Meeting', 'Exercise',
            'Chores', 'Commute', 'Rest/Entertain', 'Sleep'
        ]
        
        # 初始化每日数据存储结构
        days_in_month = (datetime(year + (month // 12), (month % 12) + 1, 1) - 
                        datetime(year, month, 1)).days
        daily_data = {day: {'total': 0, 'data': {act: 0 for act in activity_order}} 
                    for day in range(1, days_in_month + 1)}
        
        # 填充每日数据
        for record in records:
            start = datetime.strptime(record[1], '%Y-%m-%d %H:%M:%S')
            end = datetime.strptime(record[2], '%Y-%m-%d %H:%M:%S')
            act_type = record[0]
            
            current_day = start
            while current_day.date() <= end.date():
                if current_day.month == month:
                    day_num = current_day.day
                    day_start = max(start, current_day.replace(hour=0, minute=0, second=0))
                    day_end = min(end, current_day.replace(hour=23, minute=59, second=59))
                    
                    duration = (day_end - day_start).total_seconds() / 3600
                    daily_data[day_num]['data'][act_type] += duration
                    daily_data[day_num]['total'] += duration
                
                current_day += timedelta(days=1)
        
        # 准备绘图数据（包含平均列）
        valid_days = [d for d in daily_data 
                    if daily_data[d]['total'] >= 23.9 
                    and datetime(year, month, d).date() not in covered_days]
        
        # 计算平均值
        avg_data = {act: 0 for act in activity_order}
        if valid_days:
            for act in activity_order:
                avg_data[act] = sum(daily_data[d]['data'][act] for d in valid_days) / len(valid_days)
        
        # 创建图表（包含平均列）
        fig = plt.Figure(figsize=(16, 6), dpi=100)
        ax = fig.add_subplot(111)
        
        # 调整x轴范围
        max_day = days_in_month + 1  # 为平均列留位置
        x_ticks = list(range(1, days_in_month + 1)) + [max_day]
        x_labels = [str(d) for d in range(1, days_in_month + 1)] + ['Avg']
        
        # 绘制每日数据
        for day in range(1, days_in_month + 1):
            date_obj = datetime(year, month, day).date()
            if date_obj in covered_days:
                # 绘制覆盖效果
                ax.bar(day, 24, color=pink_blue(0.08), edgecolor='white', alpha=0.6, width=0.8)
                ax.text(day, 12, "Covered", ha='center', va='center', rotation=90, color='white')
            else:
                bottom = 0
                for act in activity_order:
                    value = daily_data[day]['data'][act]
                    ax.bar(
                        day, value, 
                        bottom=bottom,
                        color=COLOR_SCHEME[act],
                        edgecolor='white',
                        width=0.8
                    )
                    bottom += value
        
        # 绘制平均列
        if valid_days:
            bottom = 0
            for act in activity_order:
                value = avg_data[act]
                ax.bar(
                    max_day, value,
                    bottom=bottom,
                    color=COLOR_SCHEME[act],
                    edgecolor='white',
                    width=0.8
                )
                bottom += value
        
        # 设置样式
        ax.set_xlabel("Day of Month")
        ax.set_ylabel("Hours")
        ax.set_title(f"Monthly Activity Distribution ({year}-{month:02d})")
        ax.set_xticks(x_ticks)
        ax.set_xticklabels(x_labels)
        ax.set_xlim(0.5, max_day + 0.5)
        ax.set_ylim(0, 24)
        ax.grid(axis='y', alpha=0.3)
        
        # 在GUI界面添加覆盖按钮（非图表内嵌）
        control_frame = ttk.Frame(parent)
        ttk.Button(
            control_frame,
            text="标记覆盖日期",
            command=lambda: self._show_cover_dialog(year, month)
        ).pack(side=tk.LEFT, padx=5)
        control_frame.pack(fill=tk.X, pady=5)
        
        # 显示图表
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
    def _cover_current_day(self, year, month):
        """处理当日覆盖操作"""
        dialog = tk.Toplevel(self)
        dialog.title("选择覆盖日期")
        dialog.geometry("300x150")
        
        ttk.Label(dialog, text="选择日期:").pack(pady=10)
        
        day_var = tk.IntVar(value=1)
        day_spin = ttk.Spinbox(
            dialog, 
            from_=1, 
            to=31, 
            textvariable=day_var,
            width=5
        )
        day_spin.pack()
        
        def confirm_cover():
            try:
                day = day_var.get()
                target_date = datetime(year, month, day).date()
                self.db.cover_day(target_date)
                self._refresh_analysis()
                dialog.destroy()
            except ValueError as e:
                messagebox.showerror("错误", f"无效日期: {str(e)}")
        
        ttk.Button(
            dialog, 
            text="确认覆盖", 
            command=confirm_cover
        ).pack(pady=10)
        
        
    def _show_cover_dialog(self, year, month):
        """显示覆盖日期对话框"""
        dialog = tk.Toplevel(self)
        dialog.title("选择覆盖日期")
        dialog.geometry("300x150")
        
        ttk.Label(dialog, text="选择日期:").pack(pady=10)
        
        day_var = tk.IntVar(value=1)
        day_spin = ttk.Spinbox(
            dialog, 
            from_=1, 
            to=31, 
            textvariable=day_var,
            width=5
        )
        day_spin.pack()
        
        def confirm_cover():
            try:
                day = day_var.get()
                target_date = datetime(year, month, day).date()
                self.db.cover_day(target_date)
                # 强制刷新分析视图
                self._refresh_analysis()
                dialog.destroy()
            except ValueError as e:
                messagebox.showerror("错误", f"无效日期: {str(e)}")
        
        ttk.Button(
            dialog, 
            text="确认覆盖", 
            command=confirm_cover
        ).pack(pady=10)

# ================= 主程序入口 =================
if __name__ == "__main__":
    app = TimeTrackerApp()
    app.mainloop()
   
# 打包成应用程序请用指令：    
# pyinstaller --onefile --windowed --name QuarterTime main.py

# 如果进行版本更新，原有数据（.db文件）可以保留使用