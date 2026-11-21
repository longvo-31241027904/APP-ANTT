# ANTT SafePack

**Mã hóa và khôi phục gói tệp** · Ứng dụng Windows của nhóm 8.

## Khởi chạy

Ứng dụng cần Windows và Python 3.14. Mở PowerShell tại thư mục gốc của repo vừa clone, rồi chạy một lần để tạo môi trường và cài thư viện.

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Bấm đúp **Chay_App.bat** trong thư mục repo hoặc khởi chạy từ PowerShell.

```powershell
.\.venv\Scripts\python.exe app.py
```

## Sử dụng

- **Mã hóa** tạo gói .7z dùng AES-256 và mã hóa tên tệp. Mặc định là LZMA2 preset 1. Bạn có thể chuyển sang Store và chọn vị trí lưu mới. SafePack mở và khôi phục các gói cũ định dạng `APP ANTT CKI/1`.
- **Khám phá và khôi phục** đọc manifest để hiển thị cây và kích thước tệp. **Kiểm tra gói** đối chiếu SHA-256 mà không xuất bản giải nén. **So sánh thư mục** đếm các tệp còn nguyên, đã sửa, mới thêm, bị thiếu theo đường dẫn tương đối và SHA-256. Có thể chọn nhiều tệp bằng Ctrl hoặc Shift. Khi khôi phục, ứng dụng giữ cấu trúc thư mục, xác minh phạm vi đã chọn và yêu cầu đích mới.
- **So sánh cấu hình** mặc định đo 5 cặp cho mỗi chế độ Store và LZMA2 preset 1. Mỗi cặp dùng cùng dữ liệu và py7zr, gồm một lượt đối chứng và một lượt AES-256 có mã hóa tên tệp. Thứ tự đổi sau mỗi cặp. Gói và bản khôi phục thử chỉ dùng thư mục tạm của phiên.

## Cách đọc số đo

Tạo gói tính thời gian ghi và đóng gói .7z từ một bản kiểm kê nguồn dùng chung. Khôi phục tính thời gian mở, kiểm tra đường dẫn và giải nén ra tệp tạm. Kiểm SHA-256 tính thời gian đọc lại dữ liệu trên đĩa để đối chiếu với manifest. Các khoảng đo dùng đồng hồ đơn điệu. Thông lượng là dung lượng gốc tính theo MiB chia cho thời gian trung bình của công đoạn.

Bảng tổng hợp và biểu đồ dùng các cặp có cả hai lượt đạt. Độ lệch chuẩn mẫu của chênh lệch theo cặp cần ít nhất hai cặp hợp lệ. Chi phí mã hóa so sánh hai trung bình và bao gồm mã hóa tên tệp. Tiết kiệm dung lượng tính theo tỷ lệ kích thước gói trên dữ liệu gốc. Mẫu số bằng 0 hiển thị **Chưa đủ dữ liệu**. CSV chứa từng lượt, thời gian, số byte, số tệp đã kiểm và khớp SHA-256, trạng thái và lý do lỗi. CSV không chứa mật khẩu.

Đề xuất dùng các lượt AES-256 đã xác minh trên chính bộ dữ liệu vừa đo. Chế độ phải có kích thước gói lớn nhất quan sát được nằm trong giới hạn MiB. Trong các chế độ đạt, SafePack chọn thời gian tạo trung bình thấp nhất. **Dùng cấu hình này** chuyển chế độ và nguồn mẫu sang Mã hóa rồi mở hộp thoại chọn nơi lưu.

## Demo ba tệp

1. Tạo thư mục mẫu ngoài dự án chứa ba tệp, ví dụ `ghichu.txt`, `dulieu.csv` và `tai-lieu/doctruoc.txt`.
2. Trong **So sánh cấu hình**, chọn thư mục đó và chạy đo. Xem bảng từng lượt, hai biểu đồ và xuất CSV. Đặt giới hạn 20 MiB và bấm **Dùng cấu hình này** nếu có đề xuất. Chọn đích bên ngoài thư mục mẫu rồi tạo gói có mật khẩu.
3. Sửa `ghichu.txt` và thêm `moi.txt`. Mở gói trong **Khám phá và khôi phục**, bấm **Kiểm tra gói**, rồi so sánh với thư mục mẫu. Kết quả dự kiến là hai tệp còn nguyên, một đã sửa, một mới thêm và không thiếu tệp.
4. Trở lại **Nội dung gói**, chọn `ghichu.txt`. Bấm **Khôi phục tệp đã chọn**, đặt một thư mục đầu ra mới và kiểm tra bản cũ cùng kết quả SHA-256 1/1.

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest -v
```
