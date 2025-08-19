from odoo import fields, models

class PosConfig(models.Model):
    _inherit = 'pos.config'

    seller_ntn_cnic = fields.Char(string="Seller NTN/CNIC")
    seller_business_name = fields.Char(string="Seller Business Name")
    seller_province = fields.Selection(
        selection=[('Punjab', 'Punjab'), ('Sindh', 'Sindh'), ('Khyber Pakhtunkhwa', 'Khyber Pakhtunkhwa'), ('Balochistan', 'Balochistan'), ('Islamabad', 'Islamabad'), ('Azad Kashmir', 'Azad Kashmir'), ('Gilgit-Baltistan', 'Gilgit-Baltistan')],
        string="Seller Province"
    )
    seller_address = fields.Char(string="Seller Address")
    buyer_province = fields.Selection(
        selection=[('Punjab', 'Punjab'), ('Sindh', 'Sindh'), ('Khyber Pakhtunkhwa', 'Khyber Pakhtunkhwa'), ('Balochistan', 'Balochistan'), ('Islamabad', 'Islamabad'), ('Azad Kashmir', 'Azad Kashmir'), ('Gilgit-Baltistan', 'Gilgit-Baltistan')],
        string="Buyer Province"
    )
    enable_fbr_integration = fields.Boolean(string="Enable FBR Integration")
    fbr_token_url = fields.Char(string="Product URL")
    fbr_bearer_token = fields.Char(string="FBR Bearer Token")
    fbr_pos_server_fee = fields.Float(
        string='FBR POS Server Fee',
        default=0.0,
        help='Fixed fee charged by FBR for POS transactions, included in the invoice total.',
        config_parameter='fbr.pos_server_fee'
    )
    fbr_taxes_registered = fields.Many2many(
        'account.tax',
        'pos_config_fbr_taxes_registered_rel',
        'config_id',
        'tax_id',
        string="Taxes for Registered Customers",
        help="Taxes to apply for registered customers (with VAT)."
    )
    show_all_taxes_in_print = fields.Boolean(
        string="Show All Taxes in Print",
        help="If enabled, all taxes will be shown in the POS receipt."
    )

    taxes_to_show_in_print = fields.Many2many(
        'account.tax',
        'pos_config_tax_rel',
        'config_id', 'tax_id',
        string="Taxes to Show in Print",
        help="Select specific taxes to display in the POS receipt lines."
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
        config_parameter='fbr.annexure_id',
        help='Sales Annexure ID for HS Code, used to fetch unit of measure from FBR.'
    )
    pos_service_fee_product_id = fields.Many2one(
        'product.product',
        string='POS Service Fee Product',
        domain=[('default_code', '=', 'SERVICE_FEE')],
    )
    e_invoicing = fields.Boolean(
        string='Enable E-Invoicing',
        default=False,
        help='Enable e-invoicing feature for this POS configuration.'
    )