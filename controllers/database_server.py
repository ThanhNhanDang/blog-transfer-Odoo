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

        auth_response_data = session_data.json()
        if not (auth_response_data.get("result") and auth_response_data["result"].get("uid")):
            return False

        session_id = session_data.cookies['session_id']
        return session_id

    def callAPI(self, domain, headers, data):
        try:
            response = requests.post(
                f"{domain}/web/dataset/call_kw",
                headers=headers,
                json=data
            )
            # Kiểm tra HTTP status
            response.raise_for_status()  # Raise exception for 4XX/5XX status
            result = response.json()

            if result.get('error'):
                _logger.error(f"Error fetching tags: {result['error']}")
                return {
                    'status': 'error',
                    'message': f"Error fetching tags: {result['error']}"}

            return result

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return {
                    'status': '404',
                    'message': 'API endpoint not found. Please check the domain URL or if the API path has changed.'}
            return {
                'status': 'HTTPError',
                'message': f'HTTP Error: {e.response.status_code}'
            }
        except Exception as e:
            _logger.error(f"Error syncing remote tags: {str(e)}")
            return {
                'status': 'Exception',
                'message': f"Error syncing remote tags: {str(e)}"
            }

    @http.route('/api/compute/sync/tag', type='json', auth='user', methods=["POST"], csrf=False)
    def _sync_remote_tags(self, **kw):
        if not kw['session']:
            return False
        # Lấy tags từ server từ xa
        headers = {
            'Content-Type': 'application/json',
            'Cookie': "session_id="+kw['session']
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
            response = self.callAPI(kw['domain'], headers, data)
            if not response.get('result', False):
                if response['status'] == '404':
                    session_id = self.action_login(
                        kw["domain"], kw["database"], kw["username"], kw["password"]
                    )
                    headers.update({'Cookie': f'session_id={session_id}'})
                    response = self.callAPI(kw['domain'], headers, data)
                    response.update({"session": session_id})
                else:
                    return False
            return response

        except Exception as e:
            _logger.error(f"Error syncing remote tags: {str(e)}")
            return False

    @http.route('/api/sync/tag', type='http', auth='user', methods=["POST"], csrf=False)
    def sync_tag(self, **kw):
        try:
            # Login vào server từ xa
            session_id = self.action_login(
                kw["domain"], kw["database"], kw["username"], kw["password"]
            )
            if not session_id:
                return Response(
                    json.dumps({
                        "status": "error",
                        "message": "Sai Username hoặc Password",
                    }),
                    content_type='application/json;charset=utf-8',
                    status=400
                )

            request.env['server'].browse(int(kw['server_id'])).write({
                'username': kw["username"],
                'session': session_id,
                'database': kw["database"],
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
