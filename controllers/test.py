# -*- coding: utf-8 -*-
# Khai báo encoding để hỗ trợ ký tự Unicode

# Import các module cần thiết từ Odoo
from odoo import http  # Module để xử lý HTTP requests
from odoo.http import request, Response  # request để truy cập environment, Response để tạo HTTP response
import json  # Module để xử lý JSON

class ProductTemplateAPI(http.Controller):
    # Định nghĩa class kế thừa từ http.Controller để tạo REST API
    
    @http.route('/api/product.template', auth='user', type='http', methods=['GET'])
    # Decorator định nghĩa route, yêu cầu xác thực user, kiểu HTTP, method GET
    def get_products(self, **kwargs):
        """Get all products or filter by parameters"""
        try:
            domain = []  # List chứa các điều kiện tìm kiếm
            
            # Xử lý các tham số tìm kiếm từ request
            if kwargs.get('name'):
                # Thêm điều kiện tìm kiếm theo tên (ilike = case insensitive LIKE)
                domain.append(('name', 'ilike', kwargs.get('name')))
            if kwargs.get('default_code'):
                # Thêm điều kiện tìm kiếm theo mã sản phẩm (exact match)
                domain.append(('default_code', '=', kwargs.get('default_code')))
                
            # Thực hiện tìm kiếm sản phẩm với các điều kiện đã định nghĩa
            products = request.env['product.template'].search_read(
                domain=domain,  # Điều kiện tìm kiếm
                fields=[  # Danh sách các trường cần lấy
                    'id', 'name', 'default_code', 'list_price', 'standard_price', 
                    'categ_id', 'type', 'uom_id', 'description'
                ]
            )
            
            # Trả về kết quả dạng JSON
            return Response(
                json.dumps({'status': 'success', 'data': products}),
                content_type='application/json'
            )
            
        except Exception as e:
            # Xử lý lỗi và trả về message lỗi
            return Response(
                json.dumps({'status': 'error', 'message': str(e)}),
                content_type='application/json',
                status=500  # HTTP 500 Internal Server Error
            )

    @http.route('/api/product.template/<int:product_id>', auth='user', type='http', methods=['GET'])
    # Route để lấy thông tin một sản phẩm cụ thể theo ID
    def get_product(self, product_id, **kwargs):
        """Get single product by ID"""
        try:
            # Tìm sản phẩm theo ID và đọc các trường thông tin
            product = request.env['product.template'].browse(product_id).read([
                'name', 'default_code', 'list_price', 'standard_price',
                'categ_id', 'type', 'uom_id', 'description'
            ])
            
            if product:
                # Nếu tìm thấy sản phẩm, trả về thông tin
                return Response(
                    json.dumps({'status': 'success', 'data': product[0]}),
                    content_type='application/json'
                )
            else:
                # Nếu không tìm thấy, trả về lỗi 404
                return Response(
                    json.dumps({'status': 'error', 'message': 'Product not found'}),
                    content_type='application/json',
                    status=404
                )
                
        except Exception as e:
            # Xử lý các lỗi khác
            return Response(
                json.dumps({'status': 'error', 'message': str(e)}),
                content_type='application/json',
                status=500
            )

    @http.route('/api/product.template', auth='user', type='json', methods=['POST'])
    # Route để tạo sản phẩm mới, type='json' tự động xử lý JSON request/response
    def create_product(self, **kwargs):
        """Create new product"""
        try:
            # Kiểm tra các trường bắt buộc
            required_fields = ['name']
            for field in required_fields:
                if field not in kwargs:
                    return {'status': 'error', 'message': f'Missing required field: {field}'}
            
            # Tạo sản phẩm mới với các giá trị từ request
            new_product = request.env['product.template'].create({
                'name': kwargs.get('name'),
                'default_code': kwargs.get('default_code'),
                'list_price': kwargs.get('list_price', 0.0),  # Giá bán
                'standard_price': kwargs.get('standard_price', 0.0),  # Giá vốn
                'type': kwargs.get('type', 'product'),  # Loại sản phẩm
                'description': kwargs.get('description'),
            })
            
            # Trả về thông tin sản phẩm vừa tạo
            return {
                'status': 'success',
                'data': {
                    'id': new_product.id,
                    'name': new_product.name
                }
            }
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/product.template/<int:product_id>', auth='user', type='json', methods=['PUT'])
    # Route để cập nhật sản phẩm theo ID
    def update_product(self, product_id, **kwargs):
        """Update existing product"""
        try:
            # Tìm sản phẩm theo ID
            product = request.env['product.template'].browse(product_id)
            if not product.exists():
                return {'status': 'error', 'message': 'Product not found'}
            
            # Chuẩn bị giá trị cập nhật từ request
            update_values = {}
            for field in ['name', 'default_code', 'list_price', 'standard_price', 'type', 'description']:
                if field in kwargs:
                    update_values[field] = kwargs[field]
            
            # Thực hiện cập nhật sản phẩm
            product.write(update_values)
            
            # Trả về thông tin sau khi cập nhật
            return {
                'status': 'success',
                'data': {
                    'id': product.id,
                    'name': product.name
                }
            }
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/product.template/<int:product_id>', auth='user', type='http', methods=['DELETE'])
    # Route để xóa sản phẩm theo ID
    def delete_product(self, product_id, **kwargs):
        """Delete product"""
        try:
            # Tìm sản phẩm theo ID
            product = request.env['product.template'].browse(product_id)
            if not product.exists():
                # Nếu không tìm thấy, trả về lỗi 404
                return Response(
                    json.dumps({'status': 'error', 'message': 'Product not found'}),
                    content_type='application/json',
                    status=404
                )
            
            # Thực hiện xóa sản phẩm
            product.unlink()
            
            # Trả về thông báo thành công
            return Response(
                json.dumps({'status': 'success', 'message': 'Product deleted successfully'}),
                content_type='application/json'
            )
            
        except Exception as e:
            # Xử lý các lỗi khác
            return Response(
                json.dumps({'status': 'error', 'message': str(e)}),
                content_type='application/json',
                status=500
            )