# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Blog",
    "version": "1.0",
    "category": "Accounting/Payment Providers",
    "sequence": 0,
    "summary": "A Vietnam payment provider.",
    "description": " ",  # Non-empty string to avoid loading the README file.
    "author": "",
    "depends": ["base", "web", "website_blog"],
    "data": [  # Do no change the order
        "security/ir.model.access.csv",
        "views/serverView.xml",
        "views/blog_transfer.xml",
        "views/menuItems.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": True,
    "license": "LGPL-3",

    'assets': {
        'web.assets_backend':
        [
            'blogV2/static/src/js/*.js',
            'blogV2/static/src/xml/*.xml',
        ]
    }

}
