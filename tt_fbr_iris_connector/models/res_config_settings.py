from odoo import fields, models

class ResConfigSettings(models.Model):
    _inherit = 'res.config.settings'

    seller_ntn_cnic = fields.Char(string="Seller NTN/CNIC", related="pos_config_id.seller_ntn_cnic", readonly=False)
    seller_business_name = fields.Char(string="Seller Business Name", related="pos_config_id.seller_business_name", readonly=False)
    seller_province = fields.Selection(
        selection=[('Punjab', 'Punjab'), ('Sindh', 'Sindh'), ('Khyber Pakhtunkhwa', 'Khyber Pakhtunkhwa'), ('Balochistan', 'Balochistan'), ('Islamabad', 'Islamabad'), ('Azad Kashmir', 'Azad Kashmir'), ('Gilgit-Baltistan', 'Gilgit-Baltistan')],
        string="Seller Province",
        related="pos_config_id.seller_province",
        readonly=False
    )
    seller_address = fields.Char(string="Seller Address", related="pos_config_id.seller_address", readonly=False)
    buyer_province = fields.Selection(
        selection=[('Punjab', 'Punjab'), ('Sindh', 'Sindh'), ('Khyber Pakhtunkhwa', 'Khyber Pakhtunkhwa'), ('Balochistan', 'Balochistan'), ('Islamabad', 'Islamabad'), ('Azad Kashmir', 'Azad Kashmir'), ('Gilgit-Baltistan', 'Gilgit-Baltistan')],
        string="Buyer Province",
        related="pos_config_id.buyer_province",
        readonly=False
    )
    enable_fbr_integration = fields.Boolean(string="Enable FBR Integration", related="pos_config_id.enable_fbr_integration", readonly=False)
    fbr_token_url = fields.Char(string="Product URL", related="pos_config_id.fbr_token_url", readonly=False)
    fbr_bearer_token = fields.Char(string="FBR Bearer Token", related="pos_config_id.fbr_bearer_token", readonly=False)
    fbr_pos_server_fee = fields.Float(
        string='FBR POS Server Fee',
        default=0.0,
        help='Fixed fee charged by FBR for POS transactions, included in the invoice total.',
        related="pos_config_id.fbr_pos_server_fee",
        readonly=False
    )
    fbr_taxes_registered = fields.Many2many(
        'account.tax',
        'pos_config_fbr_taxes_registered_rel',
        'config_id',
        'tax_id',
        string="Taxes for Registered Customers",
        help="Taxes to apply for registered customers (with VAT)."
    )
    fbr_taxes_unregistered = fields.Many2many(
        'account.tax',
        'pos_config_fbr_taxes_unregistered_rel',
        'config_id',
        'tax_id',
        string="Taxes for Unregistered Customers",
        help="Taxes to apply for unregistered customers (without VAT)."
    )
    fbr_annexure_id = fields.Char(
        string='Annexure ID',
        default='3',
        required=True,
        related="pos_config_id.fbr_annexure_id",
        readonly=False,
        help='Sales Annexure ID for HS Code, used to fetch unit of measure from FBR.'
    )
    pos_service_fee_product_id = fields.Many2one(
        'product.product',
        string='POS Service Fee Product',
        domain=[('default_code', '=', 'SERVICE_FEE')],
        related="pos_config_id.pos_service_fee_product_id",
        readonly=False
    )
    e_invoicing = fields.Boolean(
        string='Enable E-Invoicing',
        default=False,
        help='Enable e-invoicing feature for this POS configuration.',
        related="pos_config_id.e_invoicing",
        readonly=False
    )