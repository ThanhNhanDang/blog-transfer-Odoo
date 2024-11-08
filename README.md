# Odoo Blog API Controller

A Python controller for managing blog posts in Odoo, with advanced image handling capabilities.

## Features

- Create and update blog posts
- Automatic image processing and optimization
- Preserve image attributes during processing
- Support for both inline images and CSS background images
- Image deduplication using MD5 hash checking
- Session-based authentication
- Tag management support

## API Usage

### Create/Update Blog Post For Specific domain name

**Endpoint:** `/api/create/blog`  
**Method:** POST  
**Authentication:** User authentication required

**Request Parameters:**
```json
{
    "blog_folder": "Technology",
    "title": "My Blog Post",
    "content": "<p>Blog content with <img src='/path/to/image.jpg' alt='test'></p>",
    "server_tag_ids": [1, 2, 3],
    "domain": "https://your-odoo-domain.com",
    "database": "your_database",
    "username": "your_username",
    "password": "your_password"
}
```

**Response:**
```json
{
    "message": "Blog post created successfully",
    "status": "success",
    "data": {
        "blog_post_server_id": 123
    }
}
```

### Image Processing Features
- Automatic upload of external images to Odoo server
- Image deduplication based on MD5 hash
- Preservation of HTML attributes during image processing
- Support for both `<img>` tags and CSS `url()` images
- Original source URL tracking in attachment descriptions

## Code Structure for 

```
blogV2/
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   └── create_blog.py
└── static/
    └── description/
        └── icon.png
```

## Key Components

### BlogController Class

Main controller class handling blog operations:

1. **Authentication Methods:**
   - `action_login`: Handles user authentication
   - `call_external_api`: Manages API calls to Odoo

2. **Image Processing:**
   - `_get_image_hash`: Generates MD5 hash for images
   - `_get_existing_attachment`: Checks for duplicate images
   - `_upload_image_to_server`: Handles image uploads
   - `_process_images_in_content`: Processes images in blog content

3. **Content Management:**
   - `_clean_content`: Sanitizes and formats blog content
   - `create_blog`: Main method for blog post creation/update

## Image Processing Flow

1. Content is received with image references
2. Each image is processed:
   - Original attributes are preserved
   - Image is downloaded and hashed
   - Duplicate check is performed
   - Image is uploaded if new or modified
   - URLs are updated in content
3. Both src and data-original-src attributes are updated
4. All other HTML attributes are preserved

## Security Considerations

- Session-based authentication required
- CSRF protection enabled
- Secure image processing with validation
- Error logging for debugging
- Input sanitization

## Error Handling

The controller includes comprehensive error handling:
- Authentication failures
- Image processing errors
- API call failures
- Missing required fields
- Tag management errors

## Logging

Logging is implemented using Odoo's logging system:
```python
_logger = logging.getLogger(__name__)
```

Key events logged:
- Authentication attempts
- Image processing results
- API call responses
- Error conditions

## Contributing

## Support

For support and issues, please create an issue in the repository or contact [nhan.dang.dev@gmail.com].