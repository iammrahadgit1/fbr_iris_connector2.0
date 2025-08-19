{
    'name': 'IRIS FBR CONNECTOR',
    'version': '1.0',
    'category': 'Point of Sale',
    'summary': 'Integrates Odoo POS with FBR Digital Invoicing for grocery stores in Pakistan',
    'description': """
        This module integrates Odoo POS with the Federal Board of Revenue (FBR) Digital Invoicing API for grocery stores.

        Features:
        - Auto-submit POS orders to FBR portal
        - Validate HS Codes and UOMs using FBR APIs
        - Handle connectivity issues with cron-based retries
        - Print FBR invoice number and QR code on receipts
        - Support for grocery store products (KG, Piece, Unit)
    """,
    'author': 'Ahad Rasool TezzTareen',
    'website': 'https://tezztareen.com/',
    'price': 150.00,  # USD price for Odoo App Store
    'currency': 'USD',
    'images': [
        'static/description/1.png', 
        'static/description/2.png', 
        'static/description/3.png', 
        'static/description/4.png', 
        'static/description/5.png', 
        'static/description/6.png', 
        'static/description/7.png', 
        'static/description/8.png', 
        'static/description/9.png', 
    ],
    'depends': ['point_of_sale', 'product', 'stock', 'base'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_company.xml',
        'views/product_template_views.xml',
        'views/res_partner.xml',
        'views/view_pos_config.xml',
        'views/pos_order.xml',
        'data/product_data.xml',
        'views/account_move.xml',   
        'views/account_tax.xml',
        'views/fbr_options.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'tt_fbr_iris_connector/static/src/app/models.js',
            'tt_fbr_iris_connector/static/src/js/shape.js',
            'tt_fbr_iris_connector/static/src/js/get_customer.js',
            'tt_fbr_iris_connector/static/src/xml/OrderReceipt.xml',
            'tt_fbr_iris_connector/static/src/js/pos_service_fee.js',
        ],
    },
    # 'pre_init_hook': 'pre_init_check',
    'post_init_hook': 'load_fbr_data_after_install',
    'post_init_hook': '_compute_fbr_rates_for_existing_products',
    'auto_install': False,
    'application': True,
}
