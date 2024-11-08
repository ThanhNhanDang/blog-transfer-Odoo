from odoo import models, fields, api, _  # Nhập các mô-đun cần thiết từ Odoo
from odoo.exceptions import UserError  # Nhập ngoại lệ UserError để xử lý lỗi
import requests  # Nhập thư viện requests để thực hiện các yêu cầu HTTP
import logging  # Nhập thư viện logging để ghi lại thông tin và lỗi

_logger = logging.getLogger(__name__)  # Tạo logger để ghi lại thông tin

# Định nghĩa class cho Server


class ServerTag(models.Model):
    _name = 'server.tag'  # Định nghĩa tên model là 'server'
    _description = 'server tag'  # Mô tả ngắn về model

    name = fields.Char(string="Server Tag", required=True)
    server_id = fields.Many2one(
        'server',  ondelete='cascade', string='Server')
    local_tag_ids = fields.Many2many(
        'blog.tag', string='Local Blog Tag')
    tag_server_id = fields.Integer(string='Tag Server Id', readonly=True)
    
    
