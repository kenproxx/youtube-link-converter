# YouTube Link Converter — IDM

Ứng dụng Windows chuyển danh sách link video YouTube thành link tải trực tiếp bằng **yt-dlp**. Giao diện tiếng Việt, chọn đúng chất lượng, tên file theo tên video, xuất TXT/thêm link vào IDM, hoặc tự tải và ghép hình/tiếng thành MP4.

## Sử dụng

1. Mở `YouTubeLinkConverter.exe` trên Windows 10/11 x64.
2. Dán mỗi dòng một link video, hoặc chọn **Nhập TXT** (UTF-8).
3. Chọn **Tốt nhất có thể / 360p / 480p / 720p / 1080p**.
4. Để tải 1080p đủ tiếng, bấm **Tải MP4 đủ tiếng**, chọn thư mục lưu. App lấy đúng video, tải thêm âm thanh nếu bị tách luồng, rồi tự ghép MP4. Xem tiến độ tải từng luồng/ghép file; chọn dòng kết quả để xem đường dẫn đã lưu.
5. Để chỉ lấy URL cho IDM/TXT, bấm **Lấy link IDM**. Chế độ này chỉ nhận một URL đã có sẵn cả hình và tiếng, nên có thể không có 1080p. Xem bảng kết quả/lỗi để biết các mức tìm thấy.
6. Với kết quả URL, chọn các dòng cần dùng, hoặc bỏ chọn tất cả để thao tác với mọi kết quả thành công:
   - **Sao chép link**.
   - **Xuất TXT**: **mỗi URL một dòng, phân cách bằng dấu xuống dòng**, không thêm tiêu đề, tên file hay dòng lỗi; UTF-8.
   - **Thêm vào IDM**: chọn `IDMan.exe` nếu chưa tự nhận diện. App truyền URL và tên video qua `/d`, `/f`, `/a`. Mở IDM để chạy hàng đợi; app không tự bắt đầu tải.

Chọn chất lượng là yêu cầu **đúng mức đó**: chọn 1080p thì chỉ nhận 1080p, không lấy 720p, 360p hoặc mức cao hơn. Không có định dạng đạt yêu cầu thì báo lỗi và không cho xuất TXT/sao chép/gửi IDM với link sai chất lượng. **Tốt nhất có thể** chọn mức cao nhất trong các định dạng phù hợp với chế độ đang dùng. Với tải MP4, bao gồm cả video/âm thanh riêng; với link IDM, chỉ gồm định dạng một URL có đủ hình/tiếng. Với video dọc, chất lượng tính theo cạnh ngắn theo quy ước `res` của yt-dlp: `360×640` = 360p, `1080×1920` = 1080p. Bảng hiển thị cả mức chất lượng và kích thước gốc khi biết đầy đủ. Đổi lựa chọn chất lượng cần chuyển đổi lại để tạo link mới. Chỉ nhận video đơn lẻ; không tự mở rộng playlist, link trùng ID được bỏ qua. Nút dừng có tác dụng sau video hiện tại.

## Lỗi “Sign in to confirm you're not a bot”

Đây là phản hồi xác minh từ YouTube. Ứng dụng hỗ trợ dùng phiên cookie của bạn theo cơ chế chính thức của yt-dlp:

1. Mở video bị lỗi trên trình duyệt **cùng máy/mạng**; hoàn tất xác minh hoặc đăng nhập nếu YouTube yêu cầu.
2. Trong **Xác thực YouTube**, chọn **Firefox**, **Chrome** hoặc **Edge** đang mở được video. Mặc định ứng dụng **Không dùng cookie**, không tự đọc trình duyệt. Nếu cần, nhập tên thư mục/đường dẫn hồ sơ; để trống để yt-dlp tự tìm. Với Firefox, xem đường dẫn thư mục hồ sơ tại `about:profiles`; Chrome/Edge xem Profile Path tại `chrome://version` / `edge://version`.
3. Chạy lại **Lấy link IDM** hoặc **Tải MP4 đủ tiếng**. Lỗi và hướng dẫn sẽ tự hiện ở phần chi tiết.
4. Nếu Chrome/Edge báo khóa database/không giải mã được cookie, đóng hoàn toàn trình duyệt rồi thử lại. Các bản Chromium trên Windows có thể dùng mã hóa mà yt-dlp không đọc được; dùng **Firefox**, hoặc xuất cookie **youtube.com** theo định dạng **Netscape cookies.txt** rồi chọn **File cookies.txt → Chọn cookies.txt**. Không dùng JSON hay file danh sách link.

Cookie chỉ được dùng khi chọn nguồn và bắt đầu xử lý. Phiên được giữ trong bộ nhớ và dùng chung khi đọc metadata, tải hình và tải tiếng; không ghi lại file cookie gốc, không lưu lựa chọn sau khi đóng ứng dụng, không xuất cookie vào TXT/IDM. Khi đọc trình duyệt, yt-dlp tạo bản sao database tạm rồi tự dọn. File cookie chứa thông tin phiên đăng nhập: giữ trên máy, không gửi lên GitHub hay chia sẻ. Link media cần cookie sẽ được hướng dẫn dùng **Tải MP4 đủ tiếng**; chế độ IDM không truyền thông tin đăng nhập ra ngoài.

Nếu vẫn gặp xác minh, xuất cookie mới từ phiên đang xem được video và thử lại sau. Cookie không bảo đảm giải quyết chặn IP/giới hạn từ YouTube; app không tự giải CAPTCHA. Không cần cài thêm thư viện Python để dùng tính năng này. Bấm **Hướng dẫn** trong app hoặc xem [FAQ cookie chính thức](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp) và [cách xuất cookie YouTube](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies).

## File EXE độc lập, đóng gói như facebook-scheduler

Dùng `build.bat` + PyInstaller `--onefile --windowed`, giống quy trình của `kenproxx/facebook-scheduler`. Kết quả:

```text
dist\YouTubeLinkConverter.exe
```

File EXE kèm Python, Tcl/Tk, yt-dlp và các thư viện mặc định (gồm EJS), chứng chỉ CA, **Deno 2.5.6** và FFmpeg từ wheel `imageio-ffmpeg==0.7.0`. Deno được tải từ release chính thức, đối chiếu SHA-256 công bố trước khi nhúng vào EXE. Không tải runtime hay mã giải thử thách từ xa khi app chạy. Người dùng không phải cài Python, pip, thư viện hay Deno. FFmpeg đã được nhúng để tự ghép MP4; không cần người dùng cài FFmpeg hoặc thêm PATH. Bước kiểm tra từ EXE cũng chạy FFmpeg để phát hiện thiếu binary đóng gói. IDM là phần mềm riêng cần có nếu dùng nút gửi sang IDM.

**Máy build** cần Windows 10/11 x64, PowerShell 5.1 trở lên, mạng tới python.org/PyPI/GitHub và chạy:

```bat
build.bat
```

Script kiểm tra Python 3.12 x64 thật sự chạy được (không chỉ kiểm tra có launcher `py`). Nếu thiếu, tự tải Python 3.12.10 chính thức từ python.org, xác minh chữ ký Authenticode hợp lệ của **Python Software Foundation**, rồi cài vào `.build-tools/python312` cho người dùng hiện tại, không thêm PATH hay tạo shortcut. Nếu chữ ký hoặc bước cài không hợp lệ, build dừng ngay và không chạy đường dẫn Python chưa tồn tại. Môi trường `.build-venv` tạo dở/sai phiên bản được giữ thành `.build-venv.backup-*` trước khi tạo lại. Script sau đó tạo `.build-venv`, cài phụ thuộc, chạy test, tải/kiểm tra Deno, build và chạy `--self-check` từ chính EXE. Kiểm tra phiên bản runtime, dữ liệu Tcl, khởi tạo cửa sổ Tk ẩn và các file JS EJS bên trong gói. Dừng build nếu lỗi. Các tệp tải xuống là đầu ra build, không commit.

Nếu máy bị chặn tải/cài Python, cài Python 3.12 x64 có Tcl/Tk từ python.org hoặc dùng artifact của GitHub Actions. Có thể dùng `py install 3.12` nếu launcher trên máy hỗ trợ Python Install Manager, sau đó chạy lại `build.bat`. Chỉ máy build cần Python; người chạy EXE hoàn chỉnh không cần cài.

Cửa sổ build chia rõ 6 bước. Khi tải Deno, tiến độ cập nhật khoảng mỗi giây: phần trăm và MiB (nếu máy chủ cung cấp dung lượng), tốc độ trung bình, ETA và thời gian đã chờ; không có dung lượng thì ghi rõ chưa biết tổng số byte. Trạng thái kết nối/chờ dữ liệu vẫn cập nhật. Tải có timeout kết nối/đọc 15 giây, giới hạn không có dữ liệu 30 giây, tối đa 10 phút mỗi lượt và tối đa 2 lượt cho lỗi mạng tạm thời. Lỗi chứng chỉ hoặc truy cập bị từ chối không bị che bằng retry. Sau khi tải, màn hình báo riêng kiểm tra SHA-256, giải nén và sẵn sàng.

Archive Deno được lưu ở `.build-tools/downloads` sau khi xác minh. Lần build sau vẫn lấy checksum chính thức và kiểm tra cache; nếu khớp thì bỏ qua tải archive. Python bật tiến độ tải có sẵn của PowerShell; khi cài đặt sẽ hiện thời gian đã chạy mỗi giây, thay vì phần trăm giả. Log cài Python ở `.build-tools/python-install.log`. Pip cũng được bật thanh tiến độ tải.

Có sẵn workflow **Build Windows EXE** trong `.github/workflows/build-windows.yml`, chạy trên Windows khi push vào `main`, tạo tag `v*`, mở PR vào `main`, hoặc chạy thủ công bằng `workflow_dispatch`. Tải EXE trong artifact **YouTubeLinkConverter-windows-x64** của lần chạy thành công. Workflow không tự tạo GitHub Release. Chỉ có workflow trong source chưa đồng nghĩa đã có EXE; cần chạy build Windows thành công.

## Giới hạn cần biết

- Chế độ **Lấy link IDM** chỉ xuất link **một file có cả hình và tiếng**. YouTube thường chỉ cung cấp hình/tiếng riêng ở chất lượng cao; chọn 1080p không bảo đảm có link 1080p. Video không có định dạng đúng chất lượng sẽ báo lỗi, không thay bằng link thiếu tiếng hoặc tự hạ độ phân giải. Lỗi liệt kê mức có sẵn cho link một file và báo rõ nếu có hình đúng chất lượng nhưng âm thanh tách riêng.
- Link trực tiếp có thời hạn, có thể phụ thuộc IP/header; nên chạy ứng dụng trên cùng máy/mạng với IDM và tải sớm. Không bảo đảm mọi video đều tải được bằng IDM. Link yêu cầu Cookie/Authorization đã biết sẽ bị loại, nhưng các ràng buộc khác của YouTube vẫn có thể làm IDM từ chối.
- TXT chỉ chứa URL nên không bảo đảm IDM tự nhận đúng tên video. **Dùng nút Thêm vào IDM để truyền tên file theo video.** Các ký tự không hợp lệ trên Windows được thay thế, giữ Unicode và tránh trùng tên trong một lần chuyển đổi. Nếu YouTube yêu cầu header, chọn dòng kết quả và xem User-Agent/Referer trong phần chi tiết để cấu hình tương ứng trong IDM. Các header tùy chỉnh khác mà tích hợp IDM không truyền được sẽ bị từ chối.
- Cookie hỗ trợ qua nguồn người dùng chọn; không vượt quyền truy cập tài khoản hoặc DRM. Chưa hỗ trợ playlist hoặc livestream đang phát. Nút dừng dừng sau video hiện tại; nếu đóng trong lúc xử lý, app đợi tác vụ hiện tại kết thúc rồi đóng để không bỏ lại tiến trình ghép file.
- YouTube thay đổi thường xuyên; cập nhật bản yt-dlp/Deno và build lại khi cần. Bản EXE không tự cập nhật thư viện.

## Vì sao thường chỉ lấy được 360p và cách có 1080p đủ tiếng

Nếu dữ liệu yt-dlp nhận được có link 360p chứa cả hình và tiếng nhưng 1080p chỉ là luồng hình riêng, chế độ chuyển đổi sang **một URL** không thể biến hai luồng thành một file đã ghép trên máy chủ YouTube. Đổi client/định dạng không bảo đảm một URL 1080p có sẵn tiếng. Không nâng 360p lên 1080p hoặc ghi nhãn sai độ phân giải.

Nút **Tải MP4 đủ tiếng** xử lý trường hợp này: chọn đúng độ phân giải, ưu tiên hình AVC/MP4 và âm thanh AAC, tải cả hai rồi ghép bằng FFmpeg. Video được giữ nguyên bitstream, không scale/nâng độ phân giải; âm thanh chỉ được chuyển sang AAC khi cần để dùng trong MP4. File đầu ra được kiểm tra đủ hình/tiếng và đúng độ phân giải trước khi lưu dưới tên video. Link hết hạn hoặc thiếu đoạn HLS/DASH sẽ làm lượt tải thất bại; không chấp nhận bỏ đoạn để tạo MP4 thiếu nội dung. File cùng tên có sẵn được giữ nguyên, file mới thêm hậu tố `(2)`, `(3)`; file tạm được dọn khi thất bại. File đã tải không được xuất TXT/sao chép URL hay gửi sang IDM.

Tham khảo: [yt-dlp format selection](https://github.com/yt-dlp/yt-dlp#format-selection), [format sorting và quy ước res](https://github.com/yt-dlp/yt-dlp#sorting-formats).

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

Trên Windows, dùng `--target windows`. Test offline kiểm tra link đầu vào, lựa chọn chất lượng và bộ lọc định dạng, tên file Windows, lỗi từng video, hủy giữa các video, TXT và đối số IDM. Test giao diện cần màn hình: trên Linux đặt `DISPLAY` trỏ tới X server; trên Windows đặt `DISPLAY=windows` để bật smoke test. Test không truy cập YouTube hoặc mở IDM: dữ liệu video/âm thanh mẫu được tạo cục bộ, tải qua HTTP localhost rồi ghép/kiểm tra bằng FFmpeg để kiểm chứng luồng thật. Việc tải thật qua IDM cần kiểm tra riêng trên Windows với video hiện có quyền truy cập.
