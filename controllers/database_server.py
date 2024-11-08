from odoo import http
from odoo.http import request, Response
import json
import html
import re
import ast
import requests  # Nhập thư viện requests để thực hiện các yêu cầu HTTP
import logging  # Nhập thư viện logging để ghi lại thông tin và lỗi

_logger = logging.getLogger(__name__)  # Tạo logger để ghi lại thông tin


class DatabaseController(http.Controller):

    # Phương thức để thực hiện đăng nhập
    def action_login(self, domain, database, username, password):
        url = f"{domain}/web/session/authenticate"  # Xây dựng URL để đăng nhập
        data = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "db": database,  # Tên database
                "login": username,  # Tên người dùng
                "password": password  # Mật khẩu
            },
            "id": 1
        }
        # Gửi yêu cầu đăng nhập
        session_data = requests.post(url, json=data)  # Gửi yêu cầu POST
        session_data.json()  # Lấy dữ liệu phản hồi

        return session_data  # Trả về dữ liệu phiên làm việc

    @http.route('/api/compute/sync/tag', type='json', auth='user', methods=["POST"], csrf=False)
    def _sync_remote_tags(self, **kw):
        # Login vào server từ xa
        session_data = self.action_login(
            kw["domain"], kw["database"], kw["username"], kw["password"]
        )
        auth_response_data = session_data.json()
        if not (auth_response_data.get("result") and auth_response_data["result"].get("uid")):
            _logger.error(
                f"_sync_remote_tags Authentication failed for server")
            return False
        session_id = session_data.cookies['session_id']

        # Lấy tags từ server từ xa
        headers = {
            'Content-Type': 'application/json',
            'Cookie': f'session_id={session_id}'
        }

        data = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "model": "blog.tag",
                "method": "search_read",
                "args": [[]],
                "kwargs": {
                    "fields": ["name", "id"]
                }
            },
            "id": 2
        }

        try:
            response = requests.post(
                f"{kw['domain']}/web/dataset/call_kw",
                headers=headers,
                json=data
            )
            result = response.json()

            if result.get('error'):
                _logger.error(f"Error fetching tags: {result['error']}")
                return False

            return result.get('result', [])

        except Exception as e:
            _logger.error(f"Error syncing remote tags: {str(e)}")
            return False

    @http.route('/api/sync/tag', type='http', auth='user', methods=["POST"], csrf=False)
    def sync_tag(self, **kw):
        
        # Try cactch để bắt sự kiện nếu tồn tại domain trùng database
        try:
            request.env['server'].browse(int(kw['server_id'])).write({
                'database': kw["database"]})
        except Exception as e:
            return Response(
                json.dumps({
                    "status": "error",
                    "message": str(e),
                }),
                content_type='application/json;charset=utf-8',
                status=200  # Để iframe có thể đọc response
            )

        try:
            request.env['server'].browse(int(kw['server_id'])).write({
                'username': kw["username"],
                'password': kw["password"],
            })

            return Response(
                json.dumps({
                    "status": "success",
                    "message": "Sync completed successfully!",
                }),
                content_type='application/json;charset=utf-8',
                status=200
            )
        except Exception as e:
            return Response(
                json.dumps({
                    "status": "error",
                    "message": str(e),
                }),
                content_type='application/json;charset=utf-8',
                status=200  # Để iframe có thể đọc response
            )

    @http.route('/api/load/database', type='json', auth='user', methods=["POST"], csrf=False)
    def load_databases(self, **kw):
        if not kw['domain']:  # Kiểm tra nếu không có domain
            return {
                "message": "Domain không hợp lệ",
                "status": "error"
            }

        # Xây dựng Doamain để lấy danh sách database
        url = f"{kw['domain']}/web/database/list"

        try:
            # Gửi yêu cầu POST tới server
            response = requests.post(
                url, json={"jsonrpc": "2.0", "method": "call", "params": {}})

            if response.status_code == 200:  # Kiểm tra nếu phản hồi thành công
                result = response.json().get('result', [])  # Lấy kết quả từ phản hồi
                if result:  # Nếu có kết quả
                    return {
                        "message": "Thành công",
                        "status": "success",
                        "databases": result
                    }

            return {
                "message": "No databases found, Could you check the domain is correct?",
                "status": "error"
            }
        except Exception as e:
            _logger.info(e)
            return {
                "message": "Server Error",
                "status": "error"
            }
