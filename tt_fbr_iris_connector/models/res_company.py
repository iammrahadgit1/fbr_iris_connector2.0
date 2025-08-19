from odoo import models, fields, api

class ResCompany(models.Model):
    _inherit = 'res.company'

    # Define the new field for product PCT codes
    
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
    fbr_default_origination_supplier = fields.Char(string="FBR Default Origination Supplier")
