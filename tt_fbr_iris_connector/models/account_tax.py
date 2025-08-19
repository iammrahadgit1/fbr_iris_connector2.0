from odoo import models, fields

class AccountTax(models.Model):
    _inherit = 'account.tax'

    fbr_tax_type = fields.Selection([
        ('sales_tax', 'Sales Tax'),
        ('extra_tax', 'Extra Tax'),
        ('further_tax', 'Further Tax'),
        ('fed_payable', 'FED Payable'),
        ('withholding_tax', 'Withholding Tax'),  # Added withholding tax option
    ], string="FBR Tax Type")
    
    fbr_rate_id = fields.Many2one("fbr.option", string="FBR Rate", ondelete="set null", domain=[("type", "=", "rate")])