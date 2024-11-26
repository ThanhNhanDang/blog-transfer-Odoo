from base64 import b64encode
from odoo import models, fields, api, _  # Nhập các mô-đun cần thiết từ Odoo
from odoo.exceptions import UserError  # Nhập ngoại lệ UserError để xử lý lỗi
import requests  # Nhập thư viện requests để thực hiện các yêu cầu HTTP
import logging  # Nhập thư viện logging để ghi lại thông tin và lỗi
from urllib.parse import urlparse, urljoin
from odoo.http import request
from odoo.exceptions import ValidationError
import xmlrpc.client
_logger = logging.getLogger(__name__)  # Tạo logger để ghi lại thông tin

# Định nghĩa class cho Server


class Server(models.Model):
    _name = 'server'  # Định nghĩa tên model là 'server'
    _description = 'server'  # Mô tả ngắn về model

    name = fields.Char(string="Server Name", required=True)
    domain = fields.Char(string="Domain", required=True)
    avatar_128 = fields.Image(
        string="avatar 128", compute='_compute_avatar_128', max_width=128, max_height=128)
    image_1920 = fields.Image(string="Avatar", max_width=1920, max_height=1920)

    database = fields.Char(string="Database")
    username = fields.Char(string="Username")
    password = fields.Char(string="Password")

    server_tag_ids = fields.One2many(
        "server.tag", "server_id", string="Server Tags", compute="_compute_sync_tag"
    )

    tag_mapping_ids = fields.One2many(
        'tag.mapping', 'server_id', string='Tag Mappings', compute="_compute_sync_local_tag"
    )

    session = fields.Char(
        'Session'
    )

    def create(self, vals):
        server = self.env['server'].search(
            domain=[('name', '=', vals['name'])], limit=1)
        if server:
            raise UserError(_("Server Name already existed!"))
        new_record = super(Server, self).create(vals)
        return new_record

    def write(self, vals):
        if vals.get('name', False):
            server = self.env['server'].search(
                domain=[('name', '=', vals['name'])], limit=1)
            if server:
                raise UserError(_("Server Name already existed!"))
        new_record = super(Server, self).write(vals)
        return new_record

    def _compute_sync_tag(self):
        """Compute method cho server_tag_ids và tag_mapping_ids"""
        for record in self:
            if not record.database:
                record.server_tag_ids = [(6, 0, [])]
            else:
                try:
                    # Xử lý server tags
                    server_tag_ids = []

                    # Chuẩn bị dữ liệu để gửi
                    data = {
                        'jsonrpc': '2.0',
                        'method': 'call',
                        'params': {
                            'domain': record.domain,
                            'database': record.database,
                            'username': record.username,
                            'password': record.password,
                            'session': record.session,
                            'server_id': record.id
                        },
                        'id': None
                    }
                    remote_tags = self.call_api(data, "/api/compute/sync/tag")
                    
                    if not remote_tags:
                        record.server_tag_ids = [(6, 0, server_tag_ids)]
                        continue
                    
                    if remote_tags.get('session', False):
                        record.session = remote_tags['session']

                    if not remote_tags["result"]:
                        record.server_tag_ids = [(6, 0, server_tag_ids)]
                        continue
                    tag_server_ids_for_delete = []

                    for tag_server in remote_tags["result"]:
                        # Tìm hoặc tạo server.tag
                        server_tag = self.env['server.tag'].search([
                            ('server_id', '=', record.id),
                            ('tag_server_id', '=', tag_server['id'])
                        ], limit=1)

                        if server_tag:
                            if server_tag.name != tag_server['name']:
                                server_tag.write({
                                    'name': tag_server['name']
                                })
                        else:
                            server_tag = self.env['server.tag'].create({
                                'name': tag_server['name'],
                                'server_id': record.id,
                                'tag_server_id': tag_server['id']
                            })

                        server_tag_ids.append(server_tag.id)
                        tag_server_ids_for_delete.append(tag_server['id'])

                    # Xóa server tags không còn tồn tại
                    if tag_server_ids_for_delete:
                        obsolete_tags = self.env['server.tag'].search([
                            ('server_id', '=', record.id),
                            ('tag_server_id', 'not in', tag_server_ids_for_delete)
                        ])
                        if obsolete_tags:
                            obsolete_tags.unlink()

                    # Cập nhật các trường computed
                    record.server_tag_ids = [(6, 0, server_tag_ids)]
                except Exception as e:
                    _logger.error(
                        f"Error in _compute_sync_tag for server {record.id}: {str(e)}")

    def _compute_sync_local_tag(self):
        for record in self:
            if not record.database:
                record.tag_mapping_ids = [(6, 0, [])]
            else:
                # Lấy tất cả blog tags hiện có
                local_blog_tags = self.env['blog.tag'].search([])
                local_blog_tag_ids = []
                local_blog_tag_ids_for_delete = []
                for tag in local_blog_tags:
                    # tìm kiếm tag.mapping nếu chưa có thì tạo
                    local_tag_mapping = self.env['tag.mapping'].search(
                        [('server_id', '=', self.id), ('local_tag_id', '=', tag.id)], limit=1)
                    if not local_tag_mapping:
                        local_tag_mapping = self.env['tag.mapping'].create(
                            {"name": tag.name, "server_id": self.id, "local_tag_id": tag.id})
                        self.tag_mapping_ids = [(4, local_tag_mapping.id)]
                    local_blog_tag_ids.append(local_tag_mapping.id)
                    local_blog_tag_ids_for_delete.append(tag.id)
                # Tìm kiếm và xóa những tag mapping không có tag local với server id
                if local_blog_tag_ids != []:
                    local_tag_mapping = request.env['tag.mapping'].search(
                        [("server_id", "=", record.id), ("local_tag_id", "not in", local_blog_tag_ids_for_delete)])
                    if local_tag_mapping:
                        local_tag_mapping.unlink()
                record.tag_mapping_ids = [(6, 0, local_blog_tag_ids)]

    def _compute_avatar_128(self):
        for record in self:
            avatar = record['image_1920']
            if not avatar:
                if record.id and record[record._avatar_name_field]:
                    avatar = record._avatar_generate_svg()
                else:
                    avatar = b64encode(record._avatar_get_placeholder())
            record['avatar_128'] = avatar

    @api.onchange('domain')
    def _onchange_domain(self):
        """Chuẩn hóa domain khi người dùng nhập"""
        if self.domain:
            self.domain = self.normalize_domain(self.domain)

    def normalize_domain(self, domain):
        """Chuẩn hóa domain về format thống nhất"""
        if not domain:
            return domain

        # Chuẩn hóa domain
        # Loại bỏ khoảng trắng thừa
        domain = domain.strip()
        if not domain.startswith(('http://', 'https://')):
            domain = 'https://' + domain

        # Parse và rebuild URL để chuẩn hóa
        parsed = urlparse(domain)
        # Tạo base URL
        # Lấy hostname (và port nếu có)

        base_url = f"{parsed.scheme}://{parsed.netloc or parsed.path}"
        # Loại bỏ dấu / ở cuối
        base_url = base_url.rstrip('/')

        return base_url

    def call_api(self, data, url):
        # Lấy session của người dùng hiện tại
        session_cookie = request.httprequest.cookies.get(
            'session_id')

        # Chuẩn bị headers với session
        headers = {
            'Content-Type': 'application/json',
            'Cookie': f'session_id={session_cookie}',
            'X-Openerp-Session-Id': request.session.sid,
            'X-CSRF-Token': request.csrf_token()
        }

        # Gọi API
        response = requests.post(url=f"{self.env['ir.config_parameter'].sudo().get_param('web.base.url')}{url}", json=data, timeout=30,  headers=headers,
                                 cookies=request.httprequest.cookies)
        response_data = response.json()
        # Đồng bộ tags từ server từ xa
        return response_data.get("result", {})

    def action_load_databases(self):
        # Chuẩn bị dữ liệu để gửi
        data = {
            'jsonrpc': '2.0',
            'method': 'call',
            'params': {
                'domain': self.domain,
            },
            'id': None
        }

        response = self.call_api(data, "/api/load/database")
        if response['status'] == "error":
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Warning',
                    'message': response['message'],
                    'type': 'warning',
                    'sticky': False,
                }
            }

        action = {
            'type': 'ir.actions.client',
            'tag': "blogV2.database",
            'target': 'new',
            'name': "Load Database",
            'params': {
                'doamin': self.domain,
                'databases': response['databases'],
                'server_id': self.id,
            },
        }
        return action
