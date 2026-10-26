# YouTube Link Converter — IDM

Ứng dụng Windows chuyển danh sách link video YouTube thành link tải trực tiếp bằng **yt-dlp**. Giao diện tiếng Việt, có chọn chất lượng, tên file theo tên video, xuất TXT và thêm vào hàng đợi IDM.

## Sử dụng

1. Mở `YouTubeLinkConverter.exe` trên Windows 10/11 x64.
2. Dán mỗi dòng một link video, hoặc chọn **Nhập TXT** (UTF-8).
3. Chọn **Tốt nhất có thể / 360p / 480p / 720p / 1080p**, rồi **Chuyển đổi**.
4. Xem tên video, chất lượng thực tế, tên file và trạng thái. Chọn dòng để xem lỗi hoặc link.
5. Chọn các dòng cần dùng, hoặc bỏ chọn tất cả để thao tác với mọi kết quả thành công:
   - **Sao chép link**.
   - **Xuất TXT**: **mỗi URL một dòng, phân cách bằng dấu xuống dòng**, không thêm tiêu đề, tên file hay dòng lỗi; UTF-8.
   - **Thêm vào IDM**: chọn `IDMan.exe` nếu chưa tự nhận diện. App truyền URL và tên video qua `/d`, `/f`, `/a`. Mở IDM để chạy hàng đợi; app không tự bắt đầu tải.

Chất lượng là mức trần: chọn 720p có thể nhận 360p nếu không có bản 720p phù hợp. Bảng kết quả báo rõ khi dùng mức thấp hơn. Đổi lựa chọn chất lượng cần chuyển đổi lại để tạo link mới. Chỉ nhận video đơn lẻ; không tự mở rộng playlist, link trùng ID được bỏ qua. Nút dừng có tác dụng sau video hiện tại.

## File EXE độc lập, đóng gói như facebook-scheduler

Dùng `build.bat` + PyInstaller `--onefile --windowed`, giống quy trình của `kenproxx/facebook-scheduler`. Kết quả:

```text
dist\YouTubeLinkConverter.exe
```

File EXE kèm Python, Tcl/Tk, yt-dlp và các thư viện mặc định (gồm EJS), chứng chỉ CA và **Deno 2.5.6**. Deno được tải từ release chính thức, đối chiếu SHA-256 công bố trước khi nhúng vào EXE. Không tải runtime hay mã giải thử thách từ xa khi app chạy. Người dùng không phải cài Python, pip, thư viện hay Deno. Không cần FFmpeg vì ứng dụng chỉ chọn file đã có cả hình và tiếng, không ghép luồng. IDM là phần mềm riêng cần có nếu dùng nút gửi sang IDM.

**Máy build** cần Windows 10/11 x64, PowerShell 5.1 trở lên, mạng tới python.org/PyPI/GitHub và chạy:

```bat
build.bat
```

Script kiểm tra Python 3.12 x64 thật sự chạy được (không chỉ kiểm tra có launcher `py`). Nếu thiếu, tự tải Python 3.12.10 chính thức từ python.org, xác minh chữ ký Authenticode hợp lệ của **Python Software Foundation**, rồi cài vào `.build-tools/python312` cho người dùng hiện tại, không thêm PATH hay tạo shortcut. Nếu chữ ký hoặc bước cài không hợp lệ, build dừng ngay và không chạy đường dẫn Python chưa tồn tại. Môi trường `.build-venv` tạo dở/sai phiên bản được giữ thành `.build-venv.backup-*` trước khi tạo lại. Script sau đó tạo `.build-venv`, cài phụ thuộc, chạy test, tải/kiểm tra Deno, build và chạy `--self-check` từ chính EXE. Kiểm tra phiên bản runtime, dữ liệu Tcl, khởi tạo cửa sổ Tk ẩn và các file JS EJS bên trong gói. Dừng build nếu lỗi. Các tệp tải xuống là đầu ra build, không commit.

Nếu máy bị chặn tải/cài Python, cài Python 3.12 x64 có Tcl/Tk từ python.org hoặc dùng artifact của GitHub Actions. Có thể dùng `py install 3.12` nếu launcher trên máy hỗ trợ Python Install Manager, sau đó chạy lại `build.bat`. Chỉ máy build cần Python; người chạy EXE hoàn chỉnh không cần cài.

Có sẵn workflow **Build Windows EXE** trong `.github/workflows/build-windows.yml`, chạy trên Windows khi push vào `main`, tạo tag `v*`, mở PR vào `main`, hoặc chạy thủ công bằng `workflow_dispatch`. Tải EXE trong artifact **YouTubeLinkConverter-windows-x64** của lần chạy thành công. Workflow không tự tạo GitHub Release. Chỉ có workflow trong source chưa đồng nghĩa đã có EXE; cần chạy build Windows thành công.

## Giới hạn cần biết

- Chỉ xuất link **một file có cả hình và tiếng**. YouTube thường chỉ cung cấp hình/tiếng riêng ở chất lượng cao; chọn 1080p không bảo đảm có link 1080p. Video không có định dạng phù hợp sẽ báo lỗi, không thay bằng link thiếu tiếng.
- Link trực tiếp có thời hạn, có thể phụ thuộc IP/header; nên chạy ứng dụng trên cùng máy/mạng với IDM và tải sớm. Không bảo đảm mọi video đều tải được bằng IDM. Link yêu cầu Cookie/Authorization đã biết sẽ bị loại, nhưng các ràng buộc khác của YouTube vẫn có thể làm IDM từ chối.
- TXT chỉ chứa URL nên không bảo đảm IDM tự nhận đúng tên video. **Dùng nút Thêm vào IDM để truyền tên file theo video.** Các ký tự không hợp lệ trên Windows được thay thế, giữ Unicode và tránh trùng tên trong một lần chuyển đổi. Nếu YouTube yêu cầu header, chọn dòng kết quả và xem User-Agent/Referer trong phần chi tiết để cấu hình tương ứng trong IDM. Các header tùy chỉnh khác mà tích hợp IDM không truyền được sẽ bị từ chối.
- Chưa hỗ trợ cookie, video cần đăng nhập, playlist, livestream đang phát, ghép video/audio hoặc tải nội dung bằng app.
- YouTube thay đổi thường xuyên; cập nhật bản yt-dlp/Deno và build lại khi cần. Bản EXE không tự cập nhật thư viện.

## Phát triển và kiểm thử

```bash
python3 -m venv .venv
# Linux: .venv/bin/python; Windows: .venv\Scripts\python.exe
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python tools/prepare_deno.py --target linux
.venv/bin/python main.py
.venv/bin/python -m unittest discover -v
.venv/bin/python main.py --self-check /tmp/youtube-self-check.json
```

Trên Windows, dùng `--target windows`. Test offline kiểm tra link đầu vào, lựa chọn chất lượng và bộ lọc định dạng, tên file Windows, lỗi từng video, hủy giữa các video, TXT và đối số IDM. Test giao diện cần màn hình: trên Linux đặt `DISPLAY` trỏ tới X server; trên Windows đặt `DISPLAY=windows` để bật smoke test. Test không tải video, không mở IDM và không cần truy cập YouTube. Việc tải thật qua IDM cần kiểm tra riêng trên Windows với video hiện có quyền truy cập.
