import pytz
from datetime import datetime
import logging
import requests
from odoo.exceptions import UserError
from odoo import models, fields, api, _
from odoo import models, fields, api, _  # Nhập các mô-đun cần thiết từ Odoo
from odoo.exceptions import UserError  # Nhập ngoại lệ UserError để xử lý lỗi
import requests  # Nhập thư viện requests để thực hiện các yêu cầu HTTP
import logging  # Nhập thư viện logging để ghi lại thông tin và lỗi
from odoo.http import request
import json
_logger = logging.getLogger(__name__)  # Tạo logger để ghi lại thông tin

class BlogPost(models.Model):
    _inherit = 'blog.post'
    def write(self, vals):
        _logger.info(vals)
        new_record = super(BlogPost, self).write(vals)
        return new_record