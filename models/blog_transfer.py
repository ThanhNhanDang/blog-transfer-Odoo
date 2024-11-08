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

class BlogTransfer(models.Model):
    _name = 'blog.transfer'
    _description = 'Blog Transfer to Multiple Servers'

    name = fields.Char(string="Tên chiến dịch chuyển", required=True)

    selected_post_id = fields.Many2one(
        'blog.post', string='Selected Blog Post', store=True)

    server_mapping_id = fields.Many2one('server', string='Server Mapping')

    blog_tag_ids = fields.Many2many(
        'blog.tag',  related='selected_post_id.tag_ids', string='Tag bài viết được chọn')

    available_server_tags = fields.Many2many(
        'server.tag',
        string='Tag server được chọn',
        compute='_compute_available_server_tags',
    )

    state = fields.Selection([
        ('draft', 'Nháp'),
        ('in_progress', 'Đang chuyển'),
        ('done', 'Hoàn thành'),
        ('failed', 'Thất bại')
    ], string='Trạng thái', default='draft')

    start_time = fields.Datetime(string='Thời gian bắt đầu')
    end_time = fields.Datetime(string='Thời gian kết thúc')
    error_log = fields.Text(string='Log lỗi')

    is_error = fields.Boolean(string='Is error')

    @api.depends('selected_post_id', 'server_mapping_id')
    def _compute_available_server_tags(self):
        for record in self:
            if record.blog_tag_ids and record.server_mapping_id:
                server_tags = self.env['server.tag'].search([
                    ('local_tag_ids', 'in', record.blog_tag_ids.ids),
                    ('server_id', 'in', record.server_mapping_id.ids)
                ])

                record.available_server_tags = [(6, 0, server_tags.ids)]
            else:
                record.available_server_tags = [(6, 0, [])]

    def _call_create_blog_api(self, server, post, server_tag_ids):
        """
        Gọi API để tạo blog trên server đích
        Returns: (success, message)
        """
        try:
            # Chuẩn bị dữ liệu để gửi
            data = {
                'jsonrpc': '2.0',
                'method': 'call',
                'params': {
                    'blog_folder': post.blog_id.name,
                    'title': post.name,
                    'content': post.content,
                    'server_tag_ids': server_tag_ids,
                    'domain': server.domain,
                    'database': server.database,
                    'username': server.username,
                    'password': server.password,
                    'blog_transfer_id': self.id
                },
                'id': None
            }
            # Lấy session của người dùng hiện tại
            session_cookie = request.httprequest.cookies.get('session_id')

            # Chuẩn bị headers với session
            headers = {
                'Content-Type': 'application/json',
                'Cookie': f'session_id={session_cookie}',
                'X-Openerp-Session-Id': request.session.sid,
                'X-CSRF-Token': request.csrf_token()
            }

            # Gọi API
            response = requests.post(url=f"{self.env['ir.config_parameter'].sudo().get_param('web.base.url')}/api/create/blog", json=data, timeout=30,  headers=headers,
                                     cookies=request.httprequest.cookies)
            response_data = response.json()

            # Kiểm tra kết quả
            if response.status_code == 200:
                if response_data.get('result', {}).get('status') == "success":
                    return True, response_data.get('result', {}).get('message')
                else:
                    error_message = response_data.get('result', {}).get(
                        'message') or 'Unknown error occurred'
                    return False, f"API Error: {error_message}"
            else:
                error_message = response_data.get('result', {}).get(
                    'message') or 'Unknown error occurred'
                return False, f"API Error: {error_message}"

        except requests.exceptions.Timeout:
            return False, "API timeout error"
        except requests.exceptions.ConnectionError:
            return False, "Could not connect to server"
        except json.JSONDecodeError:
            return False, "Invalid JSON response from server"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"

    def _log_transfer_result(self, post, server, success, message):
        """
        Ghi log kết quả chuyển bài viết
        """
        timestamp = datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')
        log_message = f"[{timestamp}] Post '{post.name}' to server '{server.name}': "
        log_message += "SUCCESS" if success else "FAILED"
        log_message += f" - {message}"

        if not success:
            if self.error_log:
                self.error_log += "\n" + log_message
            else:
                self.error_log = log_message
            _logger.error(log_message)

    def action_start_transfer(self):
        self.ensure_one()

        # Validation
        if not self.selected_post_id:
            raise UserError(_("Vui lòng chọn ít nhất một bài viết để chuyển"))
        if not self.server_mapping_id:
            raise UserError(_("Vui lòng chọn ít nhất một server để chuyển"))

        # Reset counters and status
        self.write({
            'state': 'in_progress',
            'start_time': fields.Datetime.now(),
            'error_log': ''
        })
        isSuccess = False

        try:
            server = self.server_mapping_id
            post = self.selected_post_id
            try:
                # Chuẩn bị dữ liệu tags
                server_tag_ids = self.available_server_tags.mapped('tag_server_id')

                # Gọi API và xử lý kết quả
                success, message = self._call_create_blog_api(
                    server, post, server_tag_ids)

                # Ghi log và cập nhật counters
                self._log_transfer_result(
                    post, server, success, message)

                if success:
                    isSuccess = True
                else:
                    isSuccess = False
            except Exception as e:
                isSuccess = False
                self._log_transfer_result(
                    post, server, isSuccess,
                    f"Error processing post: {str(e)}"
                )

        except Exception as e:
            self._log_transfer_result(
                self.env['blog.post'], server, isSuccess,
                f"Critical error during transfer: {str(e)}"
            )

        finally:
            # Cập nhật trạng thái cuối cùng
            end_status = 'done' if isSuccess else 'failed'
            data_update = {
                'state': end_status,
                "is_error": False if isSuccess else True,
                'end_time': fields.Datetime.now(),
            }
            self.write(data_update)

            # Log tổng kết
            summary = f"""
            Transfer completed:
            - Start time: {self.start_time}
            - End time: {self.end_time}
            - Final status: {end_status}
            """
            if self.error_log:
                self.error_log += "\n\n" + summary
            else:
                self.error_log = summary
