from odoo.http import request
from odoo import models, fields, api, _  # Nhập các mô-đun cần thiết từ Odoo
from odoo.exceptions import UserError  # Nhập ngoại lệ UserError để xử lý lỗi
import requests  # Nhập thư viện requests để thực hiện các yêu cầu HTTP
import logging  # Nhập thư viện logging để ghi lại thông tin và lỗi
import json
_logger = logging.getLogger(__name__)  # Tạo logger để ghi lại thông tin

# Định nghĩa class cho Server

class TagMapping(models.Model):
    _name = 'tag.mapping'  # Định nghĩa tên model là 'server'
    _description = 'server tag'  # Mô tả ngắn về model

    name = fields.Char(string="Local Blog Tag", required=True)
    local_tag_id = fields.Many2one(
        'blog.tag', ondelete='cascade', string='Local Blog Tag')
    server_id = fields.Many2one(
        "server", ondelete='cascade', string="Server Id")

    server_tag_ids = fields.Many2many("server.tag", string="Server Blog Tags")

    # Override phương thức write mặc định của Odoo

    def write(self, vals):
        _logger.info(vals)
        # Kiểm tra việc cập nhật server_tag_ids trong vals
        # Ví dụ payload: vals["server_tag_ids"] = [[4, 13]]
        # - [4, 13]: Command 4 nghĩa là thêm mới, 13 là ID của server tag
        if vals.get("server_tag_ids", False):
            # Duyệt qua từng thay đổi trong server_tag_ids
            for server_tag in vals["server_tag_ids"]:
                local_tag_ids = []  # List chứa các command để cập nhật local_tag_ids

                # Nếu là command 4 (thêm mới)
                if server_tag[0] == 4:
                    # Thêm local tag vào server tag
                    # self.local_tag_id.id: ID của local tag trong record hiện tại
                    local_tag_ids.append((4, self.local_tag_id.id))

                # Nếu là command 3 (xóa)
                elif server_tag[0] == 3:
                    # Xóa liên kết giữa local tag và server tag
                    local_tag_ids.append((3, self.local_tag_id.id))

                # Cập nhật bảng server.tag:
                # 1. browse(server_tag[1]): Tìm record server tag theo ID
                # 2. write(): Cập nhật trường local_tag_ids của server tag đó
                self.env["server.tag"].browse(server_tag[1]).write(
                    {"local_tag_ids": local_tag_ids})

        # Gọi write() của lớp cha để thực hiện cập nhật bình thường
        new_record = super(TagMapping, self).write(vals)
        return new_record
