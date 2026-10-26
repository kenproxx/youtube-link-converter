"""Tk GUI; all widget operations remain on the main thread."""
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Thread
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from .core import QUALITY_OPTIONS, export_txt, parse_urls, run_batch
from .extractor import convert_video
from .idm import enqueue, find_idm


class ConverterApp:
    def __init__(self, root, converter=convert_video):
        self.root, self.converter = root, converter
        self.results, self.events = [], Queue()
        self.cancel, self.busy = Event(), False
        self.root.title('YouTube Link Converter — IDM')
        self.root.geometry('1080x760')
        self.root.minsize(820, 620)
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        main = ttk.Frame(root, padding=16)
        main.pack(fill='both', expand=True)
        ttk.Label(main, text='YouTube → IDM', font=('Segoe UI', 20, 'bold')).pack(anchor='w')
        ttk.Label(main, text='Dán mỗi dòng một link video YouTube. Chỉ lấy file có cả hình và tiếng.').pack(anchor='w', pady=(4, 8))
        self.input = ScrolledText(main, height=7, wrap='word', font=('Segoe UI', 10))
        self.input.pack(fill='x')
        controls = ttk.Frame(main)
        controls.pack(fill='x', pady=10)
        self.import_button = ttk.Button(controls, text='Nhập TXT', command=self.import_txt)
        self.import_button.pack(side='left')
        ttk.Label(controls, text='Chất lượng tối đa:').pack(side='left', padx=(18, 6))
        self.quality = tk.StringVar(value='Tốt nhất có thể')
        self.quality_box = ttk.Combobox(controls, textvariable=self.quality, values=list(QUALITY_OPTIONS), state='readonly', width=18)
        self.quality_box.pack(side='left')
        self.convert_button = ttk.Button(controls, text='Chuyển đổi', command=self.start_conversion)
        self.convert_button.pack(side='left', padx=10)
        self.cancel_button = ttk.Button(controls, text='Dừng sau video hiện tại', command=self.request_cancel, state='disabled')
        self.cancel_button.pack(side='left')
        self.progress = ttk.Progressbar(main, mode='determinate')
        self.progress.pack(fill='x', pady=(0, 8))
        frame = ttk.Frame(main)
        frame.pack(fill='both', expand=True)
        cols = ('title', 'quality', 'filename', 'status')
        self.table = ttk.Treeview(frame, columns=cols, show='headings', selectmode='extended')
        for col, label, width in zip(cols, ('Tên video', 'Chất lượng', 'Tên file', 'Trạng thái'), (230, 90, 240, 240)):
            self.table.heading(col, text=label)
            self.table.column(col, width=width, minwidth=70)
        scroll = ttk.Scrollbar(frame, orient='vertical', command=self.table.yview)
        hscroll = ttk.Scrollbar(frame, orient='horizontal', command=self.table.xview)
        self.table.configure(yscrollcommand=scroll.set, xscrollcommand=hscroll.set)
        self.table.grid(row=0, column=0, sticky='nsew')
        scroll.grid(row=0, column=1, sticky='ns')
        hscroll.grid(row=1, column=0, sticky='ew')
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.table.bind('<<TreeviewSelect>>', self.show_details)
        self.details = ScrolledText(main, height=3, wrap='word', state='disabled', font=('Segoe UI', 9))
        self.details.pack(fill='x', pady=8)
        actions = ttk.Frame(main)
        actions.pack(fill='x')
        self.result_buttons = []
        for label, command in [('Sao chép link', self.copy_links), ('Xuất TXT', self.save_txt), ('Thêm vào IDM', self.send_idm)]:
            b = ttk.Button(actions, text=label, command=command, state='disabled')
            b.pack(side='left', padx=(0, 8))
            self.result_buttons.append(b)
        ttk.Label(main, text='Chọn dòng để thao tác; không chọn dòng nào = tất cả kết quả thành công.').pack(anchor='w', pady=(6, 0))
        idm_row = ttk.Frame(main)
        idm_row.pack(fill='x', pady=8)
        ttk.Label(idm_row, text='IDM:').pack(side='left')
        self.idm_path = tk.StringVar(value=find_idm())
        self.idm_entry = ttk.Entry(idm_row, textvariable=self.idm_path)
        self.idm_entry.pack(side='left', fill='x', expand=True, padx=8)
        self.idm_picker = ttk.Button(idm_row, text='Chọn IDMan.exe', command=self.pick_idm)
        self.idm_picker.pack(side='left')
        self.status = tk.StringVar(value='Sẵn sàng.')
        ttk.Label(main, textvariable=self.status).pack(anchor='w')
        ttk.Label(main, text='Link có thời hạn và có thể phụ thuộc IP/header. TXT không bảo đảm tên file; dùng nút IDM để truyền tên video.',
                  wraplength=1000, foreground='#645a40').pack(anchor='w', pady=(6, 0))
        self.root.after(80, self.poll)

    def set_busy(self, busy, converting=False):
        self.busy = busy
        state = 'disabled' if busy else 'normal'
        for w in (self.convert_button, self.import_button, self.input, self.idm_entry, self.idm_picker):
            w.configure(state=state)
        self.quality_box.configure(state='disabled' if busy else 'readonly')
        self.cancel_button.configure(state='normal' if converting else 'disabled')
        for b in self.result_buttons:
            b.configure(state='normal' if not busy and any(not r.error for r in self.results) else 'disabled')

    def start_conversion(self):
        if self.busy:
            return
        urls, errors = parse_urls(self.input.get('1.0', 'end'))
        if not urls:
            messagebox.showwarning('Kiểm tra link', '\n'.join(errors[:12]) or 'Hãy nhập ít nhất một link video.', parent=self.root)
            return
        if errors:
            messagebox.showwarning('Bỏ qua dòng không hợp lệ', '\n'.join(errors[:12]), parent=self.root)
        self.results.clear()
        self.table.delete(*self.table.get_children())
        self.cancel.clear()
        self.progress.configure(maximum=len(urls), value=0)
        quality = QUALITY_OPTIONS[self.quality.get()]
        self.set_busy(True, converting=True)
        self.status.set(f'Đang xử lý {len(urls)} video — tối đa {self.quality.get()}...')
        def work():
            try:
                for r in run_batch(urls, quality, self.cancel, self.converter):
                    self.events.put(('result', r))
            finally:
                self.events.put(('done', self.cancel.is_set()))
        Thread(target=work, daemon=True).start()

    def request_cancel(self):
        self.cancel.set()
        self.cancel_button.configure(state='disabled')
        self.status.set('Sẽ dừng sau khi video hiện tại hoàn tất (các yêu cầu mạng có timeout).')

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'result':
                    i = len(self.results)
                    self.results.append(value)
                    status = 'Lỗi — chọn dòng để xem' if value.error else 'Thành công'
                    if not value.error and value.requested_quality and value.height and value.height < value.requested_quality:
                        status += ' — thấp hơn mức đã chọn'
                    self.table.insert('', 'end', iid=str(i), values=(value.title or value.source,
                        f'{value.height}p' if value.height else '—', value.filename, status))
                    self.progress.configure(value=len(self.results))
                    self.status.set(f'Đã xử lý {len(self.results)} video...')
                elif kind == 'done':
                    self.set_busy(False)
                    ok = sum(not r.error for r in self.results)
                    self.status.set(f'{"Đã dừng" if value else "Hoàn tất"}: {ok} thành công, {len(self.results) - ok} lỗi.')
                elif kind == 'idm_done':
                    self.set_busy(False)
                    count, error = value
                    self.status.set(f'Đã thêm {count} video vào hàng đợi IDM. Mở IDM để bắt đầu tải.')
                    if error:
                        messagebox.showerror('IDM', f'Đã thêm {count} video. Dừng vì lỗi: {error}', parent=self.root)
        except Empty:
            pass
        self.root.after(80, self.poll)

    def chosen_results(self):
        selected = self.table.selection()
        items = [self.results[int(i)] for i in selected] if selected else self.results
        return [r for r in items if not r.error and r.url]

    def show_details(self, event=None):
        selected = self.table.selection()
        text = ''
        if selected:
            r = self.results[int(selected[0])]
            text = f'{r.source}\n{r.error or r.url}'
        self.details.configure(state='normal')
        self.details.delete('1.0', 'end')
        self.details.insert('1.0', text)
        self.details.configure(state='disabled')

    def import_txt(self):
        path = filedialog.askopenfilename(filetypes=[('Danh sách TXT', '*.txt'), ('Tất cả', '*.*')], parent=self.root)
        if path:
            try:
                if Path(path).stat().st_size > 5 * 1024 * 1024:
                    raise ValueError('File TXT vượt quá 5 MB.')
                text = Path(path).read_text(encoding='utf-8-sig')
                self.input.insert('end', '\n' + text)
            except (OSError, ValueError) as exc:
                messagebox.showerror('Không mở được TXT', str(exc), parent=self.root)

    def copy_links(self):
        results = self.chosen_results()
        if results:
            self.root.clipboard_clear()
            self.root.clipboard_append('\n'.join(r.url for r in results))
            self.status.set(f'Đã sao chép {len(results)} link.')

    def save_txt(self):
        results = self.chosen_results()
        if not results:
            return
        path = filedialog.asksaveasfilename(defaultextension='.txt', initialfile='youtube-links.txt',
                                           filetypes=[('Danh sách TXT', '*.txt')], parent=self.root)
        if path:
            try:
                export_txt(path, results)
                self.status.set(f'Đã xuất {len(results)} link. Dùng nút IDM để giữ tên video khi tải.')
            except OSError as exc:
                messagebox.showerror('Không lưu được TXT', str(exc), parent=self.root)

    def pick_idm(self):
        path = filedialog.askopenfilename(title='Chọn IDMan.exe', filetypes=[('IDM', 'IDMan.exe')], parent=self.root)
        if path:
            self.idm_path.set(path)

    def send_idm(self):
        results, exe = self.chosen_results(), self.idm_path.get().strip()
        if not results:
            return
        if not Path(exe).is_file():
            messagebox.showwarning('Chưa tìm thấy IDM', 'Hãy chọn IDMan.exe bằng nút bên cạnh.', parent=self.root)
            return
        self.set_busy(True)
        self.status.set('Đang thêm link vào hàng đợi IDM...')
        def work():
            count, error = 0, None
            try:
                for r in results:
                    enqueue(exe, r)
                    count += 1
            except Exception as exc:
                error = str(exc)
            self.events.put(('idm_done', (count, error)))
        Thread(target=work, daemon=True).start()

    def close(self):
        if self.busy and not messagebox.askyesno('Thoát', 'Tác vụ đang chạy. Thoát ứng dụng?', parent=self.root):
            return
        self.cancel.set()
        self.root.destroy()
