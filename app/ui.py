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
from .downloader import download_video
from .auth import CookieSource


class ConverterApp:
    def __init__(self, root, converter=convert_video, downloader=download_video):
        self.root, self.converter, self.downloader = root, converter, downloader
        self.close_pending, self.mode = False, 'links'
        self.poll_after = None
        self.root.bind('<Destroy>', self._on_destroy, add='+')
        self.results, self.events = [], Queue()
        self.cancel, self.busy = Event(), False
        self.root.title('YouTube Link Converter — IDM')
        self.root.geometry('1080x820')
        self.root.minsize(980, 720)
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        main = ttk.Frame(root, padding=16)
        main.pack(fill='both', expand=True)
        ttk.Label(main, text='YouTube → IDM', font=('Segoe UI', 20, 'bold')).pack(anchor='w')
        ttk.Label(main, text='Dán mỗi dòng một video. Lấy link IDM hoặc tải/ghép MP4 có đủ hình và tiếng, đúng chất lượng.').pack(anchor='w', pady=(4, 8))
        self.input = ScrolledText(main, height=7, wrap='word', font=('Segoe UI', 10))
        self.input.pack(fill='x')
        auth_row = ttk.Frame(main)
        auth_row.pack(fill='x', pady=(10, 0))
        ttk.Label(auth_row, text='Xác thực YouTube:').pack(side='left', padx=(0, 8))
        self.cookie_mode = tk.StringVar(value='Không dùng cookie')
        self.cookie_file, self.browser_profile = tk.StringVar(), tk.StringVar()
        self.auth_box = ttk.Combobox(auth_row, textvariable=self.cookie_mode, state='readonly', width=20,
            values=('Không dùng cookie', 'Firefox', 'Chrome', 'Edge', 'File cookies.txt'))
        self.auth_box.pack(side='left')
        self.auth_box.bind('<<ComboboxSelected>>', lambda event: self.update_auth_controls())
        self.auth_hint = ttk.Label(auth_row)
        self.auth_hint.pack(side='left', padx=8)
        self.auth_entry = ttk.Entry(auth_row, width=25)
        self.auth_entry.pack(side='left', fill='x', expand=True)
        self.cookie_picker = ttk.Button(auth_row, text='Chọn cookies.txt', command=self.pick_cookies)
        self.cookie_picker.pack(side='left', padx=8)
        ttk.Button(auth_row, text='Hướng dẫn', command=self.auth_help).pack(side='left')
        self.update_auth_controls()
        controls = ttk.Frame(main)
        controls.pack(fill='x', pady=10)
        self.import_button = ttk.Button(controls, text='Nhập TXT', command=self.import_txt)
        self.import_button.pack(side='left')
        ttk.Label(controls, text='Chất lượng yêu cầu:').pack(side='left', padx=(18, 6))
        self.quality = tk.StringVar(value='Tốt nhất có thể')
        self.quality_box = ttk.Combobox(controls, textvariable=self.quality, values=list(QUALITY_OPTIONS), state='readonly', width=18)
        self.quality_box.pack(side='left')
        self.convert_button = ttk.Button(controls, text='Lấy link IDM', command=self.start_conversion)
        self.convert_button.pack(side='left', padx=8)
        self.download_button = ttk.Button(controls, text='Tải MP4 đủ tiếng', command=lambda: self.start_conversion(download=True))
        self.download_button.pack(side='left', padx=(0, 8))
        self.cancel_button = ttk.Button(controls, text='Dừng sau video', command=self.request_cancel, state='disabled')
        self.cancel_button.pack(side='left')
        self.progress = ttk.Progressbar(main, mode='determinate')
        self.progress.pack(fill='x', pady=(0, 8))
        frame = ttk.Frame(main)
        frame.pack(fill='both', expand=True)
        cols = ('title', 'quality', 'filename', 'status')
        self.table = ttk.Treeview(frame, columns=cols, show='headings', selectmode='extended')
        for col, label, width in zip(cols, ('Tên video', 'Chất lượng', 'Tên file', 'Trạng thái'), (230, 160, 240, 240)):
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
        self.details = ScrolledText(main, height=5, wrap='word', state='disabled', font=('Segoe UI', 9))
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
        ttk.Label(main, textvariable=self.status, wraplength=1000).pack(anchor='w')
        ttk.Label(main, text='1080p thường tách hình/tiếng: dùng Tải MP4 đủ tiếng. TXT/IDM chỉ dùng link có sẵn cả hình và tiếng.',
                  wraplength=1000, foreground='#645a40').pack(anchor='w', pady=(6, 0))
        self.poll_after = self.root.after(80, self.poll)

    def set_busy(self, busy, converting=False):
        self.busy = busy
        self.update_auth_controls()
        state = 'disabled' if busy else 'normal'
        for w in (self.convert_button, self.download_button, self.import_button, self.input, self.idm_entry, self.idm_picker):
            w.configure(state=state)
        self.quality_box.configure(state='disabled' if busy else 'readonly')
        self.cancel_button.configure(state='normal' if converting else 'disabled')
        for b in self.result_buttons:
            b.configure(state='normal' if not busy and any(not r.error and r.url for r in self.results) else 'disabled')

    def start_conversion(self, download=False):
        if self.busy:
            return
        try:
            auth = self.selected_auth()
        except ValueError as exc:
            messagebox.showwarning('Xác thực YouTube', str(exc), parent=self.root)
            return
        urls, errors = parse_urls(self.input.get('1.0', 'end'))
        if not urls:
            messagebox.showwarning('Kiểm tra link', '\n'.join(errors[:12]) or 'Hãy nhập ít nhất một link video.', parent=self.root)
            return
        if errors:
            messagebox.showwarning('Bỏ qua dòng không hợp lệ', '\n'.join(errors[:12]), parent=self.root)
        folder = None
        if download:
            folder = filedialog.askdirectory(title='Chọn thư mục lưu MP4', parent=self.root)
            if not folder:
                return
        self.mode = 'download' if download else 'links'
        self.results.clear()
        self.table.delete(*self.table.get_children())
        self.cancel.clear()
        self.progress.configure(maximum=len(urls), value=0)
        quality = QUALITY_OPTIONS[self.quality.get()]
        self.set_busy(True, converting=True)
        self.status.set(f'Đang xử lý {len(urls)} video — yêu cầu {self.quality.get()}...')
        def work():
            index = [0]
            auth_options = {'auth': auth} if auth is not None else {}
            def convert(url, q):
                if not download:
                    return self.converter(url, q, **auth_options)
                index[0] += 1
                def progress(message):
                    self.events.put(('download_progress', f'Video {index[0]}/{len(urls)}: {message}'))
                return self.downloader(url, q, folder, progress=progress, **auth_options)
            try:
                for r in run_batch(urls, quality, self.cancel, convert):
                    self.events.put(('result', r))
            finally:
                self.events.put(('done', self.cancel.is_set()))
        Thread(target=work, daemon=True).start()

    def request_cancel(self):
        self.cancel.set()
        self.cancel_button.configure(state='disabled')
        self.status.set('Sẽ dừng sau khi video hiện tại hoàn tất (các yêu cầu mạng có timeout).')

    def poll(self):
        self.poll_after = None
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'result':
                    i = len(self.results)
                    self.results.append(value)
                    status = 'Lỗi — chọn dòng để xem' if value.error else ('Đã lưu MP4' if value.local_path else 'Thành công')
                    if not value.error and value.requested_quality:
                        status += ' — đúng chất lượng đã chọn'
                    resolution = f'{value.quality}p' if value.quality else '—'
                    if value.width and value.height:
                        resolution += f' ({value.width}×{value.height})'
                    self.table.insert('', 'end', iid=str(i), values=(value.title or value.source,
                        resolution, value.filename, status))
                    if value.local_path or value.error:
                        self.table.selection_set(str(i))
                        self.show_details()
                    self.progress.configure(value=len(self.results))
                    self.status.set(f'Đã xử lý {len(self.results)} video...')
                elif kind == 'done':
                    self.set_busy(False)
                    ok = sum(not r.error for r in self.results)
                    unit = 'file MP4 đã lưu' if self.mode == 'download' else 'link thành công'
                    self.status.set(f'{"Đã dừng" if value else "Hoàn tất"}: {ok} {unit}, {len(self.results) - ok} lỗi.')
                elif kind == 'download_progress':
                    self.status.set(value)
                elif kind == 'idm_done':
                    self.set_busy(False)
                    count, error = value
                    self.status.set(f'Đã thêm {count} video vào hàng đợi IDM. Mở IDM để bắt đầu tải.')
                    if error:
                        messagebox.showerror('IDM', f'Đã thêm {count} video. Dừng vì lỗi: {error}', parent=self.root)
        except Empty:
            pass
        if self.close_pending and not self.busy:
            self.root.destroy()
            return
        self.poll_after = self.root.after(80, self.poll)

    def chosen_results(self):
        selected = self.table.selection()
        items = [self.results[int(i)] for i in selected] if selected else self.results
        return [r for r in items if not r.error and r.url]

    def show_details(self, event=None):
        selected = self.table.selection()
        text = ''
        if selected:
            r = self.results[int(selected[0])]
            text = f'{r.source}\n{r.error or r.local_path or r.url}'
            if not r.error and r.headers:
                text += '\nHeader có thể cần cấu hình trong IDM:\n' + '\n'.join(f'{k}: {v}' for k, v in r.headers.items())
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

    def update_auth_controls(self):
        mode = self.cookie_mode.get()
        file_mode = mode == 'File cookies.txt'
        browser_mode = mode in ('Firefox', 'Chrome', 'Edge')
        self.auth_box.configure(state='disabled' if self.busy else 'readonly')
        self.auth_entry.configure(textvariable=self.cookie_file if file_mode else self.browser_profile,
            state='disabled' if self.busy or not (file_mode or browser_mode) else 'readonly' if file_mode else 'normal')
        self.auth_hint.configure(text='File:' if file_mode else 'Hồ sơ (trống = mặc định):')
        self.cookie_picker.configure(state='normal' if file_mode and not self.busy else 'disabled')

    def selected_auth(self):
        mode = self.cookie_mode.get()
        if mode == 'Không dùng cookie':
            return None
        if mode == 'File cookies.txt':
            path = self.cookie_file.get().strip()
            if not path or not Path(path).is_file():
                raise ValueError('Hãy chọn file cookies.txt đã xuất từ YouTube bằng nút Chọn cookies.txt.')
            return CookieSource(file=path)
        return CookieSource(browser=mode.lower(), profile=self.browser_profile.get().strip() or None)

    def pick_cookies(self):
        path = filedialog.askopenfilename(title='Chọn cookie YouTube (Netscape cookies.txt)',
            filetypes=[('Cookie TXT', '*.txt'), ('Tất cả', '*.*')], parent=self.root)
        if path:
            self.cookie_file.set(path)

    def auth_help(self):
        messagebox.showinfo('Xử lý YouTube yêu cầu xác minh',
            '1. Mở video trên trình duyệt cùng máy/mạng; hoàn tất xác minh hoặc đăng nhập nếu cần.\n'
            '2. Chọn Firefox, Chrome hoặc Edge trong mục Xác thực YouTube. Có thể nhập tên/đường dẫn hồ sơ nếu dùng nhiều hồ sơ.\n'
            '3. Nếu báo lỗi đọc/giải mã cookie, đóng hoàn toàn trình duyệt rồi thử lại. Chrome/Edge trên Windows có thể chặn giải mã; '
            'hãy dùng Firefox hoặc xuất cookie youtube.com dạng Netscape, chọn File cookies.txt rồi Chọn cookies.txt.\n'
            '4. Chạy lại thao tác. Dùng Tải MP4 đủ tiếng nếu media cần cookie; TXT/IDM không chứa thông tin đăng nhập.\n\n'
            'Cookie chỉ dùng khi bạn chọn nguồn và chạy; không được lưu cấu hình hay xuất vào TXT. '
            'Không chia sẻ file cookie. Nếu vẫn bị chặn, làm mới phiên hoặc thử lại sau.\n\n'
            'Hướng dẫn chính thức:\nhttps://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies',
            parent=self.root)

    def send_idm(self):
        results, exe = self.chosen_results(), self.idm_path.get().strip()
        if not results:
            return
        if not Path(exe).is_file():
            messagebox.showwarning('Chưa tìm thấy IDM', 'Hãy chọn IDMan.exe bằng nút bên cạnh.', parent=self.root)
            return
        self.cancel.clear()
        self.set_busy(True)
        self.status.set('Đang thêm link vào hàng đợi IDM...')
        def work():
            count, error = 0, None
            try:
                for r in results:
                    if self.cancel.is_set():
                        break
                    enqueue(exe, r)
                    count += 1
            except Exception as exc:
                error = str(exc)
            self.events.put(('idm_done', (count, error)))
        Thread(target=work, daemon=True).start()

    def _on_destroy(self, event):
        if event.widget is self.root and self.poll_after is not None:
            try:
                self.root.after_cancel(self.poll_after)
            except tk.TclError:
                pass
            self.poll_after = None

    def close(self):
        if self.busy:
            if not messagebox.askyesno('Thoát', 'Dừng sau video/tác vụ hiện tại rồi tự đóng ứng dụng?', parent=self.root):
                return
            self.close_pending = True
            self.request_cancel()
            return
        self.cancel.set()
        self.root.destroy()
