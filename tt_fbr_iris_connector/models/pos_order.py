from odoo import models, fields, api
from odoo.exceptions import UserError
import requests
import json
import threading
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

class PosOrder(models.Model):
    _inherit = 'pos.order'

    fbr_invoice_number = fields.Char(string='FBR Invoice Number', readonly=True, default="3434")
    fbr_status = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted to FBR'),
        ('failed', 'Failed'),
    ], string='FBR Status', default='draft', copy=False)
    fbr_error_message = fields.Text(string='FBR Error Message', readonly=True)
    fbr_response = fields.Text(string='FBR Response', readonly=True)

    def _threaded_fbr_post(self, order_id, user_id):
        try:
            with self.env.registry.cursor() as cr:
                env = api.Environment(cr, user_id, {})
                order = env['pos.order'].browse(order_id)
                order._post_to_fbr(max_retries=2)
                cr.commit()
        except Exception as e:
            _logger.exception("FBR Posting failed in background thread: %s", str(e))
            with self.env.registry.cursor() as cr:
                env = api.Environment(cr, user_id, {})
                order = env['pos.order'].browse(order_id)
                order.write({
                    'fbr_status': 'failed',
                    'fbr_error_message': str(e),
                    'fbr_response': ''
                })
                cr.commit()

    def action_pos_order_paid(self):
        res = super(PosOrder, self).action_pos_order_paid()
        for order in self:
            if order.config_id.enable_fbr_integration is not None and order.config_id.e_invoicing:
                try:
                    order._post_to_fbr(max_retries=2)
                except Exception as e:
                    _logger.exception("FBR Posting failed: %s", str(e))
                    order.write({
                        'fbr_status': 'failed',
                        'fbr_error_message': str(e),
                        'fbr_response': ''
                    })
                    order._schedule_fbr_post()
        return res

    def _schedule_fbr_post(self):
        self.env.cr.postcommit.add(lambda: self._safe_post_to_fbr())

    def _safe_post_to_fbr(self):
        try:
            with self.env.registry.cursor() as cr:
                env = api.Environment(cr, self._uid, {})
                order = env['pos.order'].browse(self.id)
                order._post_to_fbr(max_retries=2)
                cr.commit()
        except Exception as e:
            _logger.exception("Safe FBR post failed: %s", str(e))
            with self.env.registry.cursor() as cr:
                env = api.Environment(cr, self._uid, {})
                order = env['pos.order'].browse(self.id)
                order.write({
                    'fbr_status': 'failed',
                    'fbr_error_message': str(e),
                    'fbr_response': ''
                })
                cr.commit()

    def _get_fbr_config(self):
        self.ensure_one()
        config = self.config_id
    
        return {
            'server_url': config.fbr_token_url,
            'token': config.fbr_bearer_token,
            'annexure_id': config.fbr_annexure_id or '3',
            'seller_province': config.seller_province or 'Punjab',
            'seller_address': config.seller_address or '',
            'seller_business_name': config.seller_business_name or '',
            'pos_server_fee': config.fbr_pos_server_fee or 0.0,
        }

    def _get_scenario_id(self):
        self.ensure_one()
        first_line = self.lines[0] if self.lines else None
        if first_line:
            product = first_line.product_id
            scenario_id = product.scenario_id
            if scenario_id == 'SN001':
                return 'SN002' if not self.partner_id.vat else scenario_id
            return scenario_id or ('SN002' if not self.partner_id.vat else 'SN001')  # Default scenario
        return 'SN002' if not self.partner_id.vat else 'SN001'  # Default if no lines

    def _post_to_fbr(self, max_retries=2):
        self.ensure_one()
        if self.config_id.enable_fbr_integration is None or not self.config_id.e_invoicing:
            return

        fbr_config = self._get_fbr_config()
        scenario_id = self._get_scenario_id()

        buyer_ntn_cnic = self.partner_id.vat or ''
        buyer_name = self.partner_id.name or 'Walking Customer'
        buyer_province = self.partner_id.state_id.name or 'Punjab'
        buyer_address = self.partner_id.street or 'Faisalabad'
        buyer_registration_type = 'Registered' if self.partner_id.vat else 'Unregistered'

        total_invoice_amount = round(self.amount_total + fbr_config['pos_server_fee'], 2)

        payload = {
            "invoiceType": "Sale Invoice",
            "invoiceDate": fields.Date.today().strftime('%Y-%m-%d'),
            "invoiceRefNo": self.name,
            "sellerBusinessName": fbr_config['seller_business_name'],
            "sellerProvince": fbr_config['seller_province'],
            "sellerAddress": fbr_config['seller_address'],
            "sellerNTNCNIC": self.config_id.seller_ntn_cnic or '',
            "buyerNTNCNIC": buyer_ntn_cnic,
            "buyerBusinessName": buyer_name,
            "buyerProvince": buyer_province,
            "buyerAddress": buyer_address,
            "buyerRegistrationType": buyer_registration_type,
            "paymentMode": self.payment_ids[0].payment_method_id.name if self.payment_ids else 'Cash',
            "totalInvoiceAmount": total_invoice_amount,
            "totalSalesTax": round(self.amount_tax, 2),
            "posServerFee": round(fbr_config['pos_server_fee'], 2),
            "items": self._prepare_fbr_payload(fbr_config['annexure_id']).get("Items", []),
            "scenarioId": scenario_id,  # Always include scenarioId
        }

        headers = {
            "Authorization": f"{fbr_config['token']}",
            "Content-Type": "application/json"
        }

        for attempt in range(max_retries + 1):
            try:
                _logger.info("FBR Payload: %s", json.dumps(payload, indent=2))
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
                    return
                else:
                    error_message = response_data.get('Message') or response_data.get('validationResponse', {}).get('message', 'Unknown Error')
                    if attempt < max_retries:
                        _logger.warning("FBR post attempt %d failed: %s. Retrying...", attempt + 1, error_message)
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
                    _logger.warning(error_message + ". Retrying...")
                    continue
                self.write({
                    'fbr_status': 'failed',
                    'fbr_error_message': error_message,
                    'fbr_response': ''
                })
                raise UserError(error_message)
            
    def _prepare_fbr_payload(self, annexure_id):
        lines = []
        for line in self.lines:
            product = line.product_id
            if product == self.config_id.pos_service_fee_product_id:
                continue

            hs_code = product.fbr_hs_code.code or ''
            uom = product.fbr_uom_id.name or 'Pcs'
            unit_price = line.price_unit
            quantity = line.qty
            discount = line.discount or 0.0

            # Line base value
            value_sales_excluding_st = unit_price * quantity * (1 - discount / 100)
            total_values = value_sales_excluding_st

            # Use exactly the taxes applied on this POS line (after fiscal position)
            line_taxes = line.tax_ids_after_fiscal_position

            sales_tax = line_taxes.filtered(lambda t: t.fbr_tax_type == 'sales_tax')
            extra_tax = line_taxes.filtered(lambda t: t.fbr_tax_type == 'extra_tax')
            further_tax = line_taxes.filtered(lambda t: t.fbr_tax_type == 'further_tax')
            fed_tax = line_taxes.filtered(lambda t: t.fbr_tax_type == 'fed_payable')
            withholding_tax = line_taxes.filtered(lambda t: t.fbr_tax_type == 'withholding_tax')

            # Calculate amounts
            sales_tax_applicable = value_sales_excluding_st * (sales_tax.amount / 100) if sales_tax else 0.0
            extra_tax_applicable = value_sales_excluding_st * (extra_tax.amount / 100) if extra_tax else 0.0
            further_tax_applicable = value_sales_excluding_st * (further_tax.amount / 100) if further_tax else 0.0
            fed_payable = 0.0
            if fed_tax and fed_tax.amount_type == 'fixed':
                fed_payable = fed_tax.amount * quantity
            elif fed_tax and fed_tax.amount_type == 'percent':
                fed_payable = value_sales_excluding_st * (fed_tax.amount / 100)
            withholding_tax_applicable = value_sales_excluding_st * (withholding_tax.amount / 100) if withholding_tax else 0.0

            total_values += (sales_tax_applicable + extra_tax_applicable +
                            further_tax_applicable + fed_payable +
                            withholding_tax_applicable)

            rate_display = f"{int(sales_tax.amount)}%" if sales_tax and sales_tax.amount > 0 else "0%"
            

            lines.append({
                "itemSNo": len(lines) + 1,
                "hsCode": hs_code,
                "productDescription": product.name or 'Test Item',
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
                "sroScheduleNo": product.fbr_sro_id.name or '',
                "fedPayable": round(fed_payable, 2),
                "discount": round(discount, 2),
                "saleType": product.fbr_sale_type_id.name or '',
                "sroItemSerialNo": product.fbr_sro_item_id.name
            })

        return {'Items': lines}


    def _add_pos_service_fee(self):
        """Add POS Service Fee to order if fbr_pos_server_fee is set and e_invoicing is enabled."""
        self.ensure_one()
        _logger.info("Checking POS Service Fee for order %s (e_invoicing: %s, fbr_pos_server_fee: %s)",
                    self.name, self.config_id.e_invoicing, self.config_id.fbr_pos_server_fee)
        
        if not self.config_id.e_invoicing or not self.config_id.fbr_pos_server_fee:
            _logger.info("POS Service Fee not added for order %s: e_invoicing or fbr_pos_server_fee not set", self.name)
            return

        service_fee_product = self.config_id.pos_service_fee_product_id
        if not service_fee_product:
            _logger.error("POS Service Fee Product is not configured for order %s", self.name)
            raise UserError("POS Service Fee Product is not configured in POS settings.")

        # Check if service fee product is already added
        if any(line.product_id == service_fee_product for line in self.lines):
            _logger.info("POS Service Fee already added to order %s", self.name)
            return

        # Calculate price_subtotal and price_subtotal_incl
        price_unit = self.config_id.fbr_pos_server_fee
        qty = 1.0
        discount = 0.0
        price_subtotal = price_unit * qty * (1 - discount / 100.0)
        price_subtotal_incl = price_subtotal  # No taxes, so incl and excl are same

        # Add service fee as a new order line
        _logger.info("Adding POS Service Fee to order %s with product %s and price %s",
                    self.name, service_fee_product.name, price_unit)
        try:
            self.env['pos.order.line'].create({
                'order_id': self.id,
                'product_id': service_fee_product.id,
                'price_unit': price_unit,
                'qty': qty,
                'discount': discount,
                'tax_ids': [(6, 0, [])],  # No taxes
                'price_subtotal': price_subtotal,
                'price_subtotal_incl': price_subtotal_incl,
                'name': service_fee_product.name or 'POS Service Fee',
            })
            _logger.info("POS Service Fee successfully added to order %s", self.name)
        except Exception as e:
            _logger.error("Failed to add POS Service Fee to order %s: %s", self.name, str(e))
            raise

    def action_retry_fbr_post(self):
        for order in self:
            order._post_to_fbr(max_retries=2)

    @api.model
    def send_order_to_fbr(self, order_id):
        order = self.browse(order_id)
        if not order.exists():
            return {'error': 'Order not found'}
        try:
            order._post_to_fbr(max_retries=2)
            return {
                'fbr_invoice_number': order.fbr_invoice_number,
                'fbr_status': order.fbr_status,
            }
        except Exception as e:
            return {
                'error': str(e),
                'fbr_status': order.fbr_status,
                'fbr_error_message': order.fbr_error_message,
            }