from odoo import models, fields, api

class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.depends("taxes_id", "taxes_id.fbr_tax_type", "taxes_id.fbr_rate_id")
    def _compute_fbr_rate_id(self):
        for rec in self:
            sales_tax = rec.taxes_id.filtered(
                lambda t: t.fbr_tax_type == 'sales_tax' and t.fbr_rate_id
            )
            rec.fbr_rate_id = sales_tax[:1].fbr_rate_id if sales_tax else False

    @api.onchange("taxes_id")
    def _onchange_taxes_id_set_fbr_rate(self):
        for rec in self:
            sales_tax = rec.taxes_id.filtered(
                lambda t: t.fbr_tax_type == 'sales_tax' and t.fbr_rate_id
            )
            rec.fbr_rate_id = sales_tax[:1].fbr_rate_id if sales_tax else False