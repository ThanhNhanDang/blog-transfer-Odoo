from odoo import http, _,  api, SUPERUSER_ID

from odoo.http import request, Response
import json
import html
import re
import ast
import logging
import requests
import base64
from urllib.parse import urlparse, urljoin
import os
import hashlib

_logger = logging.getLogger(__name__)


class BlogController(http.Controller):

    """
    Controller xử lý các thao tác liên quan đến blog trong Odoo.
    Bao gồm các chức năng tạo/cập nhật bài viết và xử lý hình ảnh.
    """

    def action_login(self, domain, database, username, password):
        """
        Thực hiện đăng nhập vào hệ thống Odoo thông qua API.

        Args:
            domain: Domain của server Odoo
            database: Tên database
            username: Tên đăng nhập
            password: Mật khẩu

        Returns:
            session_data: Dữ liệu phiên đăng nhập
        """
        url = f"{domain}/web/session/authenticate"
        data = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "db": database,
                "login": username,
                "password": password
            },
            "id": 1
        }
        session_data = requests.post(url, json=data)
        session_data.json()
        return session_data

    def _get_image_hash(self, image_data):
        """
        Tính toán giá trị hash của dữ liệu hình ảnh để kiểm tra thay đổi.

        Args:
            image_data: Dữ liệu nhị phân của hình ảnh

        Returns:
            str: Giá trị hash MD5 của hình ảnh
        """
        return hashlib.md5(image_data).hexdigest()

    def _get_existing_attachment(self, original_url, domain, headers):
        """
        Lấy thông tin attachment đã tồn tại dựa trên URL gốc.

        Args:
            original_url: URL gốc của hình ảnh
            domain: Domain của server Odoo
            headers: Headers cho request API

        Returns:
            dict: Thông tin attachment nếu tồn tại, None nếu không
        """
        try:
            # Tìm attachment dựa trên URL gốc trong field description
            attachment = self.call_external_api(
                "ir.attachment",
                "search_read",
                ["description", "=", original_url],
                domain,
                headers,
                {"fields": ["id", "checksum"]}
            )

            if attachment.get("result"):
                return attachment["result"][0]
            return None
        except Exception as e:
            _logger.error(f"Error getting existing attachment: {str(e)}")
            return None

    def _upload_image_to_server(self, image_data, filename, original_url, domain, headers):
        """
        Upload hình ảnh lên server Odoo và lưu trữ tham chiếu URL gốc.

        Args:
            image_data: Dữ liệu nhị phân của hình ảnh
            filename: Tên file
            original_url: URL gốc của hình ảnh
            domain: Domain của server Odoo
            headers: Headers cho request API

        Returns:
            str: URL của hình ảnh đã upload
        """
        try:
            # Kiểm tra attachment tồn tại
            existing_attachment = self._get_existing_attachment(
                original_url, domain, headers)
            _logger.info(existing_attachment)

            # Tính hash mới
            new_image_hash = self._get_image_hash(image_data)

            # Kiểm tra nếu ảnh không thay đổi
            if existing_attachment and existing_attachment.get("checksum") == new_image_hash:
                return f"{domain}/web/image/{existing_attachment['id']}"

            # Chuẩn bị dữ liệu attachment
            attachment_data = {
                'name': filename,
                'type': 'binary',
                'datas': base64.b64encode(image_data).decode('utf-8'),
                'public': True,
                'res_model': 'ir.ui.view',
                'description': original_url
            }

            if existing_attachment:
                # Cập nhật attachment cũ
                attachment_response = self.call_external_api(
                    "ir.attachment",
                    "write",
                    attachment_data,
                    domain,
                    headers,
                    {},
                    existing_attachment['id']
                )
                attachment_id = existing_attachment['id']
            else:
                # Tạo attachment mới
                attachment_response = self.call_external_api(
                    "ir.attachment",
                    "create",
                    attachment_data,
                    domain,
                    headers
                )
                attachment_id = attachment_response["result"][0]

            return f"/web/image/{attachment_id}"
        except Exception as e:
            _logger.error(f"Error uploading image: {str(e)}")
            return None

    def _process_images_in_content(self, content, domain, headers, db_name_local):
        """
        Xử lý tất cả hình ảnh trong nội dung, giữ nguyên các thuộc tính.

        Args:
            content: Nội dung HTML cần xử lý
            domain: Domain của server Odoo  
            headers: Headers cho request API

        Returns:
            str: Nội dung đã xử lý với các URL hình ảnh mới
        """
        if not content:
            return content

        def replace_image(match, db_name_local):
            """
            Hàm callback thay thế URL hình ảnh.
            Xử lý cả hình ảnh trong CSS và thẻ img.
            """
            try:
                # Xử lý ảnh trong CSS background
                if "url('" in match.group(0):
                    image_url = match.group(1)
                    if domain in image_url or "/website/static/src" in image_url or "/web/image/website" in image_url:
                        return match.group(0)
                    return f"url('{replace_image_url(image_url, db_name_local)}')"

                # Xử lý thẻ img
                full_tag = match.group(0)
                src_url = match.group(1)

                if domain in src_url or "/website/static/src" in src_url or "/web/image/website" in src_url:
                    return full_tag

                new_url = replace_image_url(src_url, db_name_local)
                if not new_url:
                    return full_tag

                # Cập nhật cả src và data-original-src
                updated_tag = re.sub(
                    r'src="[^"]*"', f'src="{new_url}"', full_tag)
                if 'data-original-src="' in updated_tag:
                    updated_tag = re.sub(
                        r'data-original-src="[^"]*"', f'data-original-src="{new_url}"', updated_tag)
                else:
                    updated_tag = updated_tag.replace(
                        f'src="{new_url}"', f'src="{new_url}" data-original-src="{new_url}"')

                return updated_tag

            except Exception as e:
                _logger.error(f"Error processing image: {str(e)}")
                return match.group(0)

        def replace_image_url(image_url, db_name_local):
            """
            Thay thế URL hình ảnh bằng cách tải và upload lại lên server.
            """
            try:
                registry = api.Registry(db_name_local)
                with registry.cursor() as cr:
                    env = api.Environment(cr, SUPERUSER_ID, {})

                    attachment = env['ir.attachment'].search(
                        [('image_src', '=', image_url)], limit=1)
                    if not attachment:
                        return None
                    image_data = base64.b64decode(attachment.datas)
                    filename = attachment.name
                    new_url = self._upload_image_to_server(
                        image_data,
                        filename,
                        image_url,
                        domain,
                        headers
                    )
                    return new_url
            except Exception as e:
                _logger.error(
                    f"Error processing image URL {image_url}: {str(e)}")
                return None

        # Xử lý ảnh trong CSS
        content = re.sub(
            r"url\('([^']+)'\)", lambda m: replace_image(m, db_name_local), content)

        # Xử lý thẻ img
        content = re.sub(
            r'<img\s+[^>]*src="([^"]+)"[^>]*>', lambda m: replace_image(m, db_name_local), content)

        return content

    def _clean_content(self, content):
        """
        Làm sạch và định dạng nội dung blog.

        Args:
            content: Nội dung cần làm sạch

        Returns:
            str: Nội dung đã được làm sạch
        """
        if not content:
            return ""

        # Giải mã HTML entities
        content = html.unescape(content)

        # Thay thế escaped newlines
        content = content.replace('\\n', '\n')

        # Sửa URL hình ảnh
        content = re.sub(r"url\(\\+'([^)]+)\\+'\)", r"url('\1')", content)

        # Chuẩn hóa newlines
        content = re.sub(r'\n\s*\n', '\n', content)

        # Xóa khoảng trắng thừa
        content = content.strip()

        # Xử lý escaped quotes
        content = content.replace("\\'", "'")

        return content

    def call_external_api(self, model, method, args, domain, headers, kwargs={}, id=0):
        """
        Gọi API external của Odoo.

        Args:
            model: Tên model Odoo
            method: Tên phương thức cần gọi
            args: Tham số cho phương thức
            domain: Domain của server
            headers: Headers cho request
            kwargs: Các tham số bổ sung
            id: ID của record (cho phương thức write)

        Returns:
            dict: Kết quả từ API
        """
        data = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "model": model,
                "method": method,
                "args": [[args]] if method != 'write' else [[id], args],
                "kwargs": kwargs
            },
            "id": 2
        }

        response = requests.post(
            f"{domain}/web/dataset/call_kw", headers=headers, json=data)
        return response.json()

    @http.route('/api/create/blog', type='json', auth='user', methods=["POST"], csrf=False)
    def create_blog(self, **kw):
        """
        API endpoint để tạo hoặc cập nhật bài viết blog.

        Args:
            kw: Các tham số từ request
                - blog_folder: Tên thư mục blog
                - title: Tiêu đề bài viết
                - content: Nội dung bài viết
                - server_tag_ids: IDs của các tag
                - domain: Domain server
                - database: Tên database
                - username: Tên đăng nhập
                - password: Mật khẩu

        Returns:
            dict: Kết quả tạo/cập nhật blog
        """
        try:
            required_fields = ['blog_folder', 'title', 'content',
                               'server_tag_ids', 'domain', 'database', 'username', 'password','db_name_local']
            for field in required_fields:
                if field not in kw:
                    return {
                        "message": f"Missing required field: {field}",
                        "status": "error"
                    }

            # Clean the content
            cleaned_content = self._clean_content(kw['content'])

            # Authentication
            session_data = self.action_login(
                kw['domain'], kw['database'], kw['username'], kw['password'])
            auth_response_data = session_data.json()

            if not (auth_response_data.get("result") and auth_response_data["result"]["uid"]):
                return {
                    "message": "Đăng nhập thất bại, sai username hoặc password!",
                    "status": "error"
                }

            session_id = session_data.cookies['session_id']
            headers = {
                'Content-Type': 'application/json',
                'Cookie': f'session_id={session_id}'
            }
            # Process and upload only modified images
            processed_content = self._process_images_in_content(
                cleaned_content, kw['domain'], headers, kw['db_name_local'])
            _logger.info(processed_content)

            # Create/find blog folder
            blog_folder = self.call_external_api("blog.blog", "search_read", [
                                                 "name", "=", kw["blog_folder"]], kw['domain'], headers, {"fields": ["id"]})

            if blog_folder.get("result", []) == []:
                blog_folder = self.call_external_api("blog.blog", "create", {
                    'name': kw["blog_folder"]
                }, kw['domain'], headers)
                blog_folder["result"] = [{"id": blog_folder["result"][0]}]

            # Create/find blog post
            blog_post = self.call_external_api("blog.post", "search_read", [
                "name", "=", kw['title']], kw['domain'], headers, {"fields": ["id"]})

            if blog_post.get("result", []) == []:
                blog_post = self.call_external_api("blog.post", "create", {
                    'blog_id': blog_folder.get("result")[0].get("id"),
                    'name': kw['title'],
                    'content': processed_content
                }, kw['domain'], headers)
                blog_post["result"] = [{"id": blog_post["result"][0]}]
            else:
                self.call_external_api("blog.post", "write", {
                    'blog_id': blog_folder.get("result")[0].get("id"),
                    'name': kw['title'],
                    'content': processed_content
                }, kw['domain'], headers, {}, blog_post["result"][0]['id'])

            blog_post_id = blog_post["result"][0]['id']

            # Handle server tags
            try:
                self.call_external_api("blog.post", "write", {
                    'tag_ids': [(6, 0, kw.get('server_tag_ids'))]
                }, kw['domain'], headers, {}, blog_post_id)
            except Exception as e:
                return {
                    "message": f"Error adding server tag {str(e)}",
                    "status": "error"
                }

            return {
                "message": "Blog post created successfully",
                "status": "success",
                "data": {
                    "blog_post_server_id": blog_post_id
                }
            }

        except Exception as e:
            _logger.error(f"Error creating blog post: {str(e)}")
            return {
                "message": f"Error creating blog post: {str(e)}",
                "status": "error"
            }
