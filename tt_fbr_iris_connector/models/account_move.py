from odoo import models, fields, api
import json
import requests
import logging
from odoo.exceptions import UserError, ValidationError
import time

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    fbr_invoice_number = fields.Char(string='FBR Invoice Number', readonly=True)
    fbr_status = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted to FBR'),
        ('failed', 'Failed'),
    ], string='FBR Status', default='draft', copy=False)
    fbr_error_message = fields.Text(string='FBR Error Message', readonly=True)
    fbr_response = fields.Text(string='FBR Response', readonly=True)

    def _get_fbr_config(self):
        """Get FBR configuration from company settings."""
        self.ensure_one()
        company = self.company_id
        if not company.enable_fbr_integration:
            raise UserError("FBR Integration is not enabled for this company.")
        if not company.fbr_token_url or not company.fbr_bearer_token:
            raise UserError("FBR Token URL or Bearer Token is missing in company settings.")
        return {
            'server_url': company.fbr_token_url.strip(),
            'token': company.fbr_bearer_token.strip(),
            'seller_province': company.seller_province or 'Punjab',
            'seller_address': company.seller_address or '',
            'seller_business_name': company.seller_business_name or company.name,
            'seller_ntn_cnic': company.seller_ntn_cnic or '',
        }

    def _get_scenario_id(self):
        """Get scenario ID based on partner registration and product settings."""
        self.ensure_one()
        first_line = self.invoice_line_ids[0] if self.invoice_line_ids else None
        if first_line:
            product = first_line.product_id
            return product.scenario_id
        return None

    def _compute_tax_amounts(self, line, base_price, quantity, discount):
        """Compute tax amounts for included/excluded taxes and fixed taxes using account.tax."""
        product = line.product_id
        buyer_registration_type = self.partner_id.fbr_registration_type or 'Unregistered'

        # Fetch taxes based on fbr_tax_type
        taxes = line.tax_ids
        sales_tax = taxes.filtered(lambda t: t.fbr_tax_type == 'sales_tax')
        extra_tax = taxes.filtered(lambda t: t.fbr_tax_type == 'extra_tax')
        further_tax = taxes.filtered(lambda t: t.fbr_tax_type == 'further_tax')
        fed_tax = taxes.filtered(lambda t: t.fbr_tax_type == 'fed_payable')  # Assuming duty maps here
        withholding_tax = taxes.filtered(lambda t: t.fbr_tax_type == 'withholding_tax')

        # Tax rates
        tax_rate = sales_tax.amount if sales_tax else 0.0
        extra_tax_rate = extra_tax.amount if extra_tax else 0.0
        further_tax_rate = further_tax.amount if further_tax and buyer_registration_type == 'Unregistered' else 0.0
        withholding_tax_rate = withholding_tax.amount if withholding_tax else 0.0

        # Base price is untaxed (as per Odoo figures)
        base_price_excl_tax = base_price
        value_sales_excluding_st = base_price_excl_tax * quantity * (1 - discount / 100)

        # Calculate taxes (excluded case)
        sales_tax_applicable = value_sales_excluding_st * (tax_rate / 100) if tax_rate > 0 else 0.0
        extra_tax_applicable = value_sales_excluding_st * (extra_tax_rate / 100) if extra_tax_rate > 0 else 0.0
        further_tax_applicable = value_sales_excluding_st * (further_tax_rate / 100) if further_tax_rate > 0 else 0.0
        withholding_tax_applicable = value_sales_excluding_st * (withholding_tax_rate / 100) if withholding_tax_rate > 0 else 0.0

        # Calculate FED/duty (assuming fixed amount for duty)
        fed_payable = 0.0
        if fed_tax and fed_tax.amount_type == 'fixed':
            fed_payable = fed_tax.amount * quantity  # 45.00 Rs as fixed duty

        total_values = (value_sales_excluding_st + sales_tax_applicable + extra_tax_applicable +
                       further_tax_applicable + withholding_tax_applicable + fed_payable)

        return {
            'value_sales_excluding_st': value_sales_excluding_st,
            'sales_tax_applicable': sales_tax_applicable,
            'extra_tax_applicable': extra_tax_applicable,
            'further_tax_applicable': further_tax_applicable,
            'withholding_tax_applicable': withholding_tax_applicable,
            'fed_payable': fed_payable,  # Maps to duty
            'total_values': total_values,
        }

    def _prepare_fbr_invoice_data(self):
        """Prepare invoice data for FBR API with tax verification."""
        self.ensure_one()
        if not self.invoice_line_ids:
            raise UserError("Cannot send invoice to FBR: No invoice lines found.")
        if not self.invoice_date:
            raise UserError("Invoice date is required for FBR submission.")
        # if not self.amount_total or not self.amount_tax:
        #     raise UserError("Total amount and tax amount must be set for FBR submission.")

        fbr_config = self._get_fbr_config()
        scenario_id = self._get_scenario_id()

        buyer_ntn_cnic = self.partner_id.ntn or ''
        buyer_name = self.partner_id.name or 'Walking Customer'
        buyer_province = self.partner_id.region or 'Unknown'
        buyer_address = self.partner_id.fbr_address or self.partner_id.street or 'Unknown'
        buyer_registration_type = self.partner_id.fbr_registration_type or 'Unregistered'

        lines = []
        total_sales_tax = 0.0
        total_extra_tax = 0.0
        total_further_tax = 0.0
        total_fed = 0.0
        total_withholding_tax = 0.0
        total_base = 0.0
        total_calculated = 0.0

        for line in self.invoice_line_ids:
            product = line.product_id
            hs_code = product.fbr_hs_code.code if product.fbr_hs_code else ''
            uom = product.fbr_uom_id.name or 'Pcs'
            unit_price = line.price_unit
            quantity = line.quantity
            discount = line.discount or 0.0

            tax_amounts = self._compute_tax_amounts(line, unit_price, quantity, discount)
            value_sales_excluding_st = tax_amounts['value_sales_excluding_st']
            sales_tax_applicable = tax_amounts['sales_tax_applicable']
            extra_tax_applicable = tax_amounts['extra_tax_applicable']
            further_tax_applicable = tax_amounts['further_tax_applicable']
            fed_payable = tax_amounts['fed_payable']  # Duty
            withholding_tax_applicable = tax_amounts['withholding_tax_applicable']
            total_values = tax_amounts['total_values']

            sales_tax = line.tax_ids.filtered(lambda t: t.fbr_tax_type == 'sales_tax')
            rate_display = sales_tax.fbr_rate_id.name if sales_tax else ""

            lines.append({
                "itemSNo": len(lines) + 1,
                "hsCode": hs_code,
                "productDescription": product.name or 'Unknown Item',
                "unitPrice": round(unit_price, 2),
                "rate": rate_display,
                "uoM": uom,
                "quantity": quantity,
                "totalValues": round(total_values, 2),
                "valueSalesExcludingST": round(value_sales_excluding_st, 2),
                "fixedNotifiedValueOrRetailPrice": round(value_sales_excluding_st, 2),
                "salesTaxApplicable": round(sales_tax_applicable, 2),
                "salesTaxWithheldAtSource": round(withholding_tax_applicable, 2),
                "extraTax": round(extra_tax_applicable, 2),
                "furtherTax": round(further_tax_applicable, 2),
                "sroScheduleNo": product.fbr_sro_id.name,
                "fedPayable": round(fed_payable, 2),  # Duty maps here
                "discount": round(discount, 2),
                "saleType": product.fbr_sale_type_id.name,
                "sroItemSerialNo": product.fbr_general_sro_item_id.name or 'other'
            })

            # Aggregate for verification
            total_base += value_sales_excluding_st
            total_sales_tax += sales_tax_applicable
            total_extra_tax += extra_tax_applicable
            total_further_tax += further_tax_applicable
            total_fed += fed_payable
            total_withholding_tax += withholding_tax_applicable
            total_calculated += total_values

        # Verification: Check if calculated totals match Odoo totals
        calculated_tax = total_sales_tax + total_extra_tax + total_further_tax + total_fed + total_withholding_tax
        if round(calculated_tax, 2) != round(self.amount_tax, 2) or round(total_calculated, 2) != round(self.amount_total, 2):
            _logger.warning("FBR tax calculation mismatch: Calculated tax %s vs Odoo %s; Total %s vs Odoo %s", calculated_tax, self.amount_tax, total_calculated, self.amount_total)

        payload = {
            "invoiceType": "Sale Invoice",
            "invoiceDate": fields.Date.to_string(self.invoice_date),
            "invoiceRefNo": self.name,
            "sellerBusinessName": fbr_config['seller_business_name'],
            "sellerProvince": fbr_config['seller_province'],
            "sellerAddress": fbr_config['seller_address'],
            "sellerNTNCNIC": fbr_config['seller_ntn_cnic'],
            "buyerNTNCNIC": buyer_ntn_cnic,
            "buyerBusinessName": buyer_name,
            "buyerProvince": buyer_province,
            "buyerAddress": buyer_address,
            "buyerRegistrationType": buyer_registration_type,
            "paymentMode": self.invoice_payment_term_id.name or 'Cash',
            "totalInvoiceAmount": round(self.amount_total, 2),  # 211.40 Rs
            "totalSalesTax": round(total_sales_tax, 2),  # 24.41 Rs
            "posServerFee": 0.0,
            "items": lines
        }

        if scenario_id:
            payload["scenarioId"] = scenario_id

        # Log payload without sensitive information
        safe_payload = payload.copy()
        safe_payload['sellerNTNCNIC'] = '****'
        safe_payload['buyerNTNCNIC'] = '****'
        _logger.info("FBR Invoice Payload: %s", json.dumps(safe_payload, indent=2))
        return payload


    def _update_invoice_lines_with_taxes(self):
        """Update invoice lines to include applicable taxes."""
        self.ensure_one()
        tax_lines = []
        fed_applicable_sales_types = self.env['ir.config_parameter'].sudo().get_param('fbr.fed_applicable_sales_types', default=[
            'Petroleum Products', 'Telecommunication services', 'Cigarettes', 'Beverages'
        ])
        for line in self.invoice_line_ids:
            product = line.product_id
            taxes = []
            # Keep existing taxes that are already in the line
            existing_taxes = line.tax_ids.filtered(lambda t: t.fbr_tax_type in ['sales_tax', 'extra_tax', 'further_tax', 'fed_payable'])
            taxes.extend(existing_taxes.ids)
            # Add further tax only for unregistered buyers if not already present
            if (self.partner_id.fbr_registration_type or 'Unregistered') == 'Unregistered':
                further_tax = self.env['account.tax'].search([('fbr_tax_type', '=', 'further_tax')], limit=1)
                if further_tax and further_tax.id not in taxes:
                    taxes.append(further_tax.id)
            if taxes:
                tax_lines.append((1, line.id, {'tax_ids': [(6, 0, taxes)]}))
                _logger.info("Updated taxes for product %s: %s", product.name, taxes)

        if tax_lines:
            self.write({'invoice_line_ids': tax_lines})

    def send_to_fbr(self):
        """Public method to send invoice to FBR."""
        self.ensure_one()
        with self.env.cr.savepoint():
            self._update_invoice_lines_with_taxes()
            return self.action_post_to_fbr()

    def action_post_to_fbr(self, max_retries=2):
        """Post the invoice to FBR API with exponential backoff."""
        self.ensure_one()
        fbr_config = self._get_fbr_config()
        payload = self._prepare_fbr_invoice_data()
        headers = {
            "Authorization": fbr_config['token'],
            "Content-Type": "application/json"
        }
        _logger.info("FBR API Request - URL: %s, Headers: %s", fbr_config['server_url'], headers)

        for attempt in range(max_retries + 1):
            try:
                response = requests.post(fbr_config['server_url'], json=payload, headers=headers, timeout=10)
                _logger.info("FBR Raw Response: %s", response.text)
                response_data = response.json() if response.text else {'Message': 'No response data'}

                if response.status_code == 200 and response_data.get('validationResponse', {}).get('statusCode') == '00':
                    self.write({
                        'fbr_invoice_number': response_data.get('invoiceNumber', ''),
                        'fbr_status': 'posted',
                        'fbr_error_message': '',
                        'fbr_response': json.dumps(response_data, indent=2)
                    })
                    return response_data
                elif response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 2 ** attempt))
                    _logger.warning("Rate limit hit. Retrying after %d seconds...", retry_after)
                    time.sleep(retry_after)
                    continue
                else:
                    error_message = response_data.get('Message') or response_data.get('validationResponse', {}).get('message', 'Unknown Error')
                    if attempt < max_retries:
                        _logger.warning("FBR post attempt %d failed: %s. Retrying after %d seconds...", attempt + 1, error_message, 2 ** attempt)
                        time.sleep(2 ** attempt)
                        continue
                    self.write({
                        'fbr_status': 'failed',
                        'fbr_error_message': error_message,
                        'fbr_response': json.dumps(response_data, indent=2)
                    })
                    raise UserError(f"FBR posting failed after {max_retries + 1} attempts: {error_message}")
            except requests.exceptions.RequestException as e:
                error_message = f"Request error (Attempt {attempt + 1}/{max_retries + 1}): {str(e)}"
                if attempt < max_retries:
                    _logger.warning(error_message + ". Retrying after %d seconds...", 2 ** attempt)
                    time.sleep(2 ** attempt)
                    continue
                self.write({
                    'fbr_status': 'failed',
                    'fbr_error_message': error_message,
                    'fbr_response': ''
                })
                raise UserError(error_message)

    # def action_post(self):
    #     """Override the default post action to include FBR posting."""
    #     self.ensure_one()
    #     with self.env.cr.savepoint():
    #         self._update_invoice_lines_with_taxes()
    #         res = super(AccountMove, self).action_post()
    #         if self.company_id.enable_fbr_integration:
    #             self.action_post_to_fbr()
    #         return res