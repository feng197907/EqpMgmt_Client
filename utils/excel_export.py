"""Excel 导出的统一出口。

导出在本项目有两种运行形态，过去每个蓝图各自实现一遍，出现了 4 份重复：

    浏览器      → 直接返回 xlsx 附件流
    pywebview 桌面壳 → 无法处理 attachment 下载，改为落盘后返回 JSON，
                      前端再调 window.pywebview.api.open_file() 打开

现在统一收敛到这里，蓝图只需一行 ``return excel_response(wb, filename)``。
"""

import os
import tempfile
from io import BytesIO

from flask import jsonify, request, send_file
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

XLSX_MIMETYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# 桌面壳（desktop_launcher.py）发起的导出会带这个请求头，
# 后端据此切换成「落盘 + 返路径」而不是「返回二进制流」。
DESKTOP_SHELL_HEADER = "X-Desktop-Shell"

# 桌面壳导出文件落地目录，放在系统临时目录下，随系统清理
EXPORT_TEMP_DIRNAME = "DMS_Exports"

_THIN_BORDER = Side(style="thin", color="000000")


def is_desktop_shell():
    """当前请求是否来自桌面壳。"""
    return request.headers.get(DESKTOP_SHELL_HEADER) == "1"


def save_excel_to_temp(wb, filename):
    """把工作簿保存到临时目录，返回绝对路径。

    同名文件会被覆盖：文件名里带时间戳到秒，实际不会冲突。
    """
    temp_dir = os.path.join(tempfile.gettempdir(), EXPORT_TEMP_DIRNAME)
    os.makedirs(temp_dir, exist_ok=True)
    filepath = os.path.join(temp_dir, filename)
    wb.save(filepath)
    return filepath


def excel_response(wb, filename):
    """统一的导出响应，自动区分浏览器与桌面壳。

    浏览器：xlsx 附件流，Content-Disposition 带文件名。
    桌面壳：JSON ``{"success": true, "filepath": ..., "filename": ...}``，
            文件已落盘，由前端调 pywebview API 打开。
    """
    if is_desktop_shell():
        filepath = save_excel_to_temp(wb, filename)
        return jsonify({"success": True, "filepath": filepath, "filename": filename})

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(
        output,
        mimetype=XLSX_MIMETYPE,
        as_attachment=True,
        download_name=filename,
    )


def style_header_cell(cell):
    """蓝色底、白色加粗、居中、细边框 —— 各导出统一表头样式。"""
    cell.font = Font(bold=True, color="FFFFFF")
    cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    cell.alignment = Alignment(horizontal="center", vertical="center")
    cell.border = Border(left=_THIN_BORDER, right=_THIN_BORDER, top=_THIN_BORDER, bottom=_THIN_BORDER)


def style_border_cell(cell):
    """给数据单元格加细边框。"""
    cell.border = Border(left=_THIN_BORDER, right=_THIN_BORDER, top=_THIN_BORDER, bottom=_THIN_BORDER)


def auto_width(ws, max_width=50, min_width=8):
    """按内容长度自适应列宽（中文按近似宽度估算）。"""
    for column_cells in ws.columns:
        col_letter = column_cells[0].column_letter
        max_len = 0
        for cell in column_cells:
            if cell.value is None:
                continue
            text = str(cell.value)
            # 中文字符占两个字符宽，粗略折算，避免中文列被压太窄
            width = sum(2 if ord(ch) > 127 else 1 for ch in text)
            max_len = max(max_len, width)
        ws.column_dimensions[col_letter].width = max(min_width, min(max_len + 2, max_width))
