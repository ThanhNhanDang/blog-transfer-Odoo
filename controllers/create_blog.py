from odoo import http
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
    def action_login(self, domain, database, username, password):
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
        """Calculate hash of image data to check for changes"""
        return hashlib.md5(image_data).hexdigest()

    def _get_existing_attachment(self, original_url, domain, headers):
        """Get existing attachment info based on original URL"""
        try:
            # Tìm attachment dựa trên URL gốc được lưu trong field description
            attachment = self.call_external_api(
                "ir.attachment",
                "search_read",
                ["description", "=", original_url],
                domain,
                headers,
                {"fields": ["id", "checksum"]}
            )
            _logger.info(attachment)

            if attachment.get("result"):
                return attachment["result"][0]

            return None
        except Exception as e:
            _logger.error(f"Error getting existing attachment: {str(e)}")
            return None

    def _upload_image_to_server(self, image_data, filename, original_url, domain, headers):
        """Upload an image to Odoo server with original URL reference"""
        try:
            # Kiểm tra xem ảnh đã tồn tại chưa
            existing_attachment = self._get_existing_attachment(
                original_url, domain, headers)
            _logger.info(existing_attachment)
            # Tính toán hash của ảnh mới
            new_image_hash = self._get_image_hash(image_data)

            # Nếu ảnh đã tồn tại và không thay đổi, trả về URL cũ
            if existing_attachment and existing_attachment.get("checksum") == new_image_hash:
                return f"{domain}/web/image/{existing_attachment['id']}"

            # Tạo attachment mới hoặc cập nhật attachment cũ
            attachment_data = {
                'name': filename,
                'type': 'binary',
                'datas': base64.b64encode(image_data).decode('utf-8'),
                'public': True,
                'res_model': 'ir.ui.view',
                'description': original_url  # Lưu URL gốc để tham chiếu sau này
            }

            if existing_attachment:
                # Cập nhật attachment hiện có
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

    def _process_images_in_content(self, content, domain, headers):
        """Process images in the content and preserve all attributes"""
        if not content:
            return content

        def replace_image(match):
            try:
                # For CSS background images
                if "url('" in match.group(0):
                    image_url = match.group(1)
                    if domain in image_url or "/website/static/src" in image_url or "/web/image/website" in image_url:
                        return match.group(0)
                    return f"url('{replace_image_url(image_url)}')"

                # For img tags
                full_tag = match.group(0)
                src_url = match.group(1)

                if domain in src_url or "/website/static/src" in src_url or "/web/image/website" in src_url:
                    return full_tag

                new_url = replace_image_url(src_url)
                if not new_url:
                    return full_tag

                # Replace both src and data-original-src while preserving all other attributes
                updated_tag = re.sub(
                    r'src="[^"]*"', f'src="{new_url}"', full_tag)
                if 'data-original-src="' in updated_tag:
                    updated_tag = re.sub(
                        r'data-original-src="[^"]*"', f'data-original-src="{new_url}"', updated_tag)
                else:
                    # Insert data-original-src right after src
                    updated_tag = updated_tag.replace(
                        f'src="{new_url}"', f'src="{new_url}" data-original-src="{new_url}"')

                return updated_tag

            except Exception as e:
                _logger.error(f"Error processing image: {str(e)}")
                return match.group(0)

        def replace_image_url(image_url):
            try:
                session_cookie_local = request.httprequest.cookies.get(
                    'session_id')
                headers_local = {
                    'Content-Type': 'application/json',
                    'Cookie': f'session_id={session_cookie_local}',
                    'X-Openerp-Session-Id': request.session.sid,
                    'X-CSRF-Token': request.csrf_token()
                }

                image_url_local = f"{request.env['ir.config_parameter'].sudo().get_param('web.base.url')}{image_url}"
                image_response = requests.get(
                    image_url_local, headers=headers_local, cookies=request.httprequest.cookies)

                if image_response.status_code != 200:
                    return None

                filename = os.path.basename(
                    urlparse(image_url_local).path) or 'image.jpg'
                new_url = self._upload_image_to_server(
                    image_response.content,
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

        # Process CSS background images
        content = re.sub(r"url\('([^']+)'\)", replace_image, content)

        # Process img tags - now matching the complete img tag to preserve attributes
        content = re.sub(
            r'<img\s+[^>]*src="([^"]+)"[^>]*>', replace_image, content)

        return content

    def _clean_content(self, content):
        """Clean and format blog content"""
        if not content:
            return ""

        # Unescape content first
        content = html.unescape(content)

        # Replace escaped newlines with actual newlines
        content = content.replace('\\n', '\n')

        # Fix image URLs - replace multiple backslashes with single
        content = re.sub(r"url\(\\+'([^)]+)\\+'\)", r"url('\1')", content)

        # Normalize newlines
        content = re.sub(r'\n\s*\n', '\n', content)

        # Remove unnecessary spaces at start/end
        content = content.strip()

        # Additional cleanup for any remaining double escaped quotes
        content = content.replace("\\'", "'")

        return content

    def call_external_api(self, model, method, args, domain, headers, kwargs={}, id=0):
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

        blog_folder_response = requests.post(
            f"{domain}/web/dataset/call_kw", headers=headers, json=data)
        blog_folder = blog_folder_response.json()
        return blog_folder

    @http.route('/api/create/blog', type='json', auth='user', methods=["POST"], csrf=False)
    def create_blog(self, **kw):
        try:
            required_fields = ['blog_folder', 'title', 'content',
                               'server_tag_ids', 'domain', 'database', 'username', 'password']
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
            _logger.info(cleaned_content)
            # Process and upload only modified images
            processed_content = self._process_images_in_content(
                cleaned_content, kw['domain'], headers)
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
