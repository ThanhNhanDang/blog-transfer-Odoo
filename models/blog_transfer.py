import xmlrpc.client
import pytz
from datetime import datetime
from dateutil.relativedelta import relativedelta
import logging
import requests
from odoo.exceptions import UserError
from odoo import models, fields, api, _
from odoo.exceptions import UserError  # Nhập ngoại lệ UserError để xử lý lỗi
import requests  # Nhập thư viện requests để thực hiện các yêu cầu HTTP
import logging  # Nhập thư viện logging để ghi lại thông tin và lỗi
from odoo.http import request
from odoo.addons.blogV2.controllers.create_blog import BlogController
import json
_logger = logging.getLogger(__name__)  # Tạo logger để ghi lại thông tin


class BlogTransfer(models.Model):
    _name = 'blog.transfer'
    _description = 'Blog Transfer to Multiple Servers'

    name = fields.Char(string="Tên chiến dịch chuyển", required=True)

    selected_post_id = fields.Many2one(
        'blog.post', string='Selected Blog Post', store=True, required=True)

    server_mapping_id = fields.Many2one(
        'server', string='Server Mapping', required=True)

    blog_tag_ids = fields.Many2many(
        'blog.tag',  related='selected_post_id.tag_ids', string='Tag bài viết được chọn')

    available_server_tags = fields.Many2many(
        'server.tag',
        string='Tag server được chọn',
    )

    state = fields.Selection([
        ('draft', 'Nháp'),
        ('in_progress', 'Đang chuyển'),
        ('done', 'Hoàn thành'),
        ('failed', 'Thất bại')
    ], string='Trạng thái', default='draft')

    start_time = fields.Datetime(string='Thời gian bắt đầu')
    end_time = fields.Datetime(string='Thời gian kết thúc')
    
    scheduled_date = fields.Datetime(
        string='Đặt thời gian dự kiến chuyển',
        required=True,
        default=lambda self: fields.Datetime.now()
    )

    blog_post_write_date = fields.Datetime(
        string='Blog Post Last Update On',  related='selected_post_id.write_date')
    server_tag_ids = fields.One2many(
        "server.tag", "server_id", string="Server Tags", related='server_mapping_id.server_tag_ids'
    )
    tag_mapping_ids = fields.One2many(
        'tag.mapping', 'server_id', string='Tag Mappings', related='server_mapping_id.tag_mapping_ids'
    )

    error_log = fields.Text(string='Log lỗi')

    is_error = fields.Boolean(string='Is error')

    # Biến class để lưu instance của controller
    _blog_controller = None
    
    @api.constrains('scheduled_date')
    def _check_scheduled_date(self):
        for record in self:
            if record.scheduled_date < fields.Datetime.now():
                raise UserError(_('Thời gian dự kiến chuyển phải lớn hơn thời gian hiện tại!'))

    @classmethod
    def get_blog_controller(self):
        """
        Singleton pattern để lấy hoặc tạo instance của BlogController
        """
        if not self._blog_controller:
            self._blog_controller = BlogController()
        return self._blog_controller

    def create(self, vals):
        current_time = fields.Datetime.now()
        if fields.Datetime.from_string(vals['scheduled_date']) < current_time:
            vals['scheduled_date'] = fields.Datetime.to_datetime(
                fields.Datetime.from_string(current_time) + relativedelta(minutes=1)
            )
        
        new_record = super(BlogTransfer, self).create(vals)

        self.env['blog.transfer.scheduler'].create({
            'name': new_record.name,
            'blog_transfer_id': new_record.id
        })
        return new_record

    @api.onchange('selected_post_id', 'server_mapping_id')
    def _onchange_available_server_tags(self):
        if self.blog_tag_ids and self.server_mapping_id:
            server_tags = self.env['server.tag'].search([
                ('local_tag_ids', 'in', self.blog_tag_ids.ids),
                ('server_id', 'in', self.server_mapping_id.ids)
            ])

            self.available_server_tags = [(6, 0, server_tags.ids)]
        else:
            self.available_server_tags = [(6, 0, [])]

    def _call_create_blog_api(self, server, post, server_tag_ids):
        """
        Gọi trực tiếp method create_blog từ BlogController
        Returns: (success, message)
        """
        try:
            # Lấy controller instance từ singleton
            blog_controller = self.get_blog_controller()
           # Chuẩn bị params
            params = {
                'blog_folder': post.blog_id.name,
                'title': post.name,
                'content': post.content,
                'server_tag_ids': server_tag_ids,
                'domain': server.domain,
                'database': server.database,
                'username': server.username,
                'password': server.password,
                'session':server.session,
                'server_id':server.id,
                'blog_transfer_id': self.id,
                'db_name_local': self.env.cr.dbname
            }

            # Gọi method create_blog
            result = blog_controller.create_blog(**params)

            # Kiểm tra kết quả
            if result.get('status') == "success":
                return True, result.get('message')
            else:
                error_message = result.get(
                    'message') or 'Unknown error occurred'
                return False, f"Error: {error_message}"

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
        error_log = ""
        if not success:
            if self.error_log:
                error_log = self.error_log + "\n" + log_message
            else:
                error_log = log_message
            self.write({'error_log': error_log})

    def action_start_transfer(self):
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
                server_tag_ids = self.available_server_tags.mapped(
                    'tag_server_id')

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

            if isSuccess:
                scheduler = self.env['blog.transfer.scheduler'].search(
                    [('blog_transfer_id', '=', self.id)], limit=1)
                if scheduler:
                    scheduler.unlink()

            self.write(data_update)

            # Log tổng kết
            summary = f"""
            Transfer completed:
            - Start time: {self.start_time}
            - End time: {self.end_time}
            - Final status: {end_status}
            """
            error_log = ""
            if self.error_log:
                error_log = self.error_log + "\n\n" + summary
            else:
                error_log = summary
            self.write({"error_log": error_log})


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'
    image_src = fields.Char(store=True)
