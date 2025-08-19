from odoo import models, fields, api
import requests
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from odoo.osv import expression
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

class FbrOption(models.Model):
    _name = "fbr.option"
    _description = "FBR API Option Cache"

    code = fields.Char(string="Code", required=True, index=True)
    name = fields.Char(string="Name", required=True)
    type = fields.Selection([
        ('province', 'Province'),
        ('doctype', 'Document Type'),
        ('hscode', 'HS Code'),
        ('uom', 'UOM'),
        ('sale_type', 'Sale Type'),
        ('rate', 'Rate'),
        ('sro', 'SRO Schedule'),
        ('sro_item', 'SRO Item'),
        ('sro_item_general', 'General SRO Item'),
    ], required=True, index=True)
    buyer_ntn = fields.Char(string="Buyer NTN")
    parent_sro_id = fields.Many2one('fbr.option', string="Parent SRO Schedule", domain=[('type', '=', 'sro')])
    last_updated = fields.Datetime(string="Last Updated", default=fields.Datetime.now)

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for record in self:
            if record.type == 'hscode':
                record.display_name = f"{record.code} - {record.name[:70]}" if record.code else record.name
            else:
                record.display_name = record.name

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        domain = ['|', ('name', operator, name), ('code', operator, name)]
        domain = expression.AND([domain, args])
        records = self.search_fetch(domain, ['display_name'], limit=limit)
        return [(record.id, record.display_name) for record in records]

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    fbr_province_id = fields.Many2one("fbr.option", string="FBR Province", ondelete="set null", domain=[("type", "=", "province")])
    fbr_document_type_id = fields.Many2one("fbr.option", string="FBR Document Type", ondelete="set null", domain=[("type", "=", "doctype")])
    fbr_hs_code = fields.Many2one("fbr.option", string="FBR HS Code", ondelete="set null", domain=[("type", "=", "hscode")])
    fbr_uom_id = fields.Many2one("fbr.option", string="FBR UOM", ondelete="set null", domain=[("type", "=", "uom")])
    fbr_sale_type_id = fields.Many2one("fbr.option", string="FBR Sale Type", ondelete="set null", domain=[("type", "=", "sale_type")])
    fbr_rate_id = fields.Many2one("fbr.option", string="FBR Rate", domain=[("type", "=", "rate")], compute="_compute_fbr_rate_id", store=True, readonly=False)
    fbr_sro_id = fields.Many2one("fbr.option", string="FBR SRO Schedule", ondelete="set null", domain=[("type", "=", "sro")])
    fbr_sro_item_id = fields.Many2one("fbr.option", string="FBR SRO Item", ondelete="set null", domain=[("type", "=", "sro_item")])
    fbr_general_sro_item_id = fields.Many2one("fbr.option", string="FBR General SRO Item", ondelete="set null", domain=[("type", "=", "sro_item_general")])

    scenario_id = fields.Selection(
        selection=[
            ('SN001', 'Scenario SN001'),
            ('SN002', 'Goods at Standard Rate (SN002)'),
            ('SN003', 'Scenario SN003'),
            ('SN004', 'Scenario SN004'),
            ('SN005', 'Scenario SN005'),
            ('SN006', 'Exempt Goods (SN006)'),
            ('SN007', 'Zero-Rated Goods (SN007)'),
            ('SN008', 'Scenario SN008'),
            ('SN009', 'Scenario SN009'),
            ('SN010', 'Scenario SN010'),
            ('SN011', 'Scenario SN011'),
            ('SN012', 'Scenario SN012'),
            ('SN013', 'Scenario SN013'),
            ('SN014', 'Scenario SN014'),
            ('SN015', 'Scenario SN015'),
            ('SN016', 'Scenario SN016'),
            ('SN017', 'Scenario SN017'),
            ('SN018', 'Scenario SN018'),
            ('SN019', 'Scenario SN019'),
            ('SN020', 'Scenario SN020'),
            ('SN021', 'Scenario SN021'),
            ('SN022', 'Scenario SN022'),
            ('SN023', 'Scenario SN023'),
            ('SN024', 'Scenario SN024'),
            ('SN025', 'Scenario SN025'),
            ('SN026', 'Retail Sale to End Consumer (SN026)'),
            ('SN027', 'Scenario SN027'),
            ('SN028', 'Scenario SN028'),
        ],
        string='FBR Tax Scenario',
        help='Select the applicable FBR IRIS tax scenario for this product.',
        default='SN002',
        required=True,
    )

    @api.depends("taxes_id", "taxes_id.fbr_tax_type", "taxes_id.fbr_rate_id")
    def _compute_fbr_rate_id(self):
        for rec in self:
            sales_tax = rec.taxes_id.filtered(lambda t: t.fbr_tax_type == 'sales_tax' and t.fbr_rate_id)
            rec.fbr_rate_id = sales_tax[:1].fbr_rate_id if sales_tax else False

    @api.onchange("taxes_id")
    def _onchange_taxes_id_set_fbr_rate(self):
        for rec in self:
            sales_tax = rec.taxes_id.filtered(lambda t: t.fbr_tax_type == 'sales_tax' and t.fbr_rate_id)
            rec.fbr_rate_id = sales_tax[:1].fbr_rate_id if sales_tax else False

    def _call_fbr_api(self, url, company):
        """Make an API call with the given company context."""
        if not company:
            _logger.error("No valid company found for API call.")
            return []
        token = company.fbr_bearer_token
        # print(token)
        if not token:
            _logger.warning(f"⚠️ FBR Bearer Token not found for company {company.name}.")
            return []
        try:
            # Ensure Bearer prefix
            headers = {"Authorization": f"{token}"}
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200:
                return res.json()
            else:
                _logger.error(f"❌ FBR API call failed [{url}]: {res.status_code} - {res.text}")
        except Exception as e:
            _logger.error(f"💥 FBR API error [{url}]: {e}")
        return []


    def _update_fbr_options(self, records, opt_type, code_key, name_key, parent_sro_id=None):
        Option = self.env["fbr.option"].sudo()  # Use sudo to bypass access issues
        _logger.debug(f"Updating FBR options for type: {opt_type}")
        
        # Fetch existing records in bulk
        existing_records = Option.search([("type", "=", opt_type)])
        existing_codes = set(existing_records.mapped("code"))
        
        # Prepare new records for bulk creation
        new_records = []
        for rec in records:
            code = str(rec.get(code_key))
            name = rec.get(name_key)
            if code and name and code not in existing_codes:
                vals = {
                    "code": code,
                    "name": name,
                    "type": opt_type,
                    "last_updated": fields.Datetime.now(),
                }
                if parent_sro_id:
                    vals['parent_sro_id'] = parent_sro_id.id
                new_records.append(vals)
        
        # Bulk create new records
        if new_records:
            Option.create(new_records)
            _logger.info(f"Added {len(new_records)} new {opt_type} options")

    def _check_cache_validity(self, opt_type, max_age_days=7):
        """Check if cached data is recent enough to skip API call."""
        Option = self.env["fbr.option"].sudo()
        last_updated = Option.search([("type", "=", opt_type)], limit=1).last_updated
        if last_updated and (datetime.now() - last_updated).days < max_age_days:
            _logger.info(f"Using cached {opt_type} data (last updated: {last_updated})")
            return True
        return False

    @api.model
    def load_fbr_static_options(self):
        """Load static dropdown data from FBR API into fbr.option table with optimizations."""
        _logger.info("Starting FBR static options load...")
        
        # Get the company context, default to the user's company or first accessible company
        company = self.env.company
        if not company or company.id not in self.env.user.company_ids.ids:
            company = self.env['res.company'].sudo().search([('id', 'in', self.env.user.company_ids.ids)], limit=1)
            if not company:
                _logger.error("No accessible company found for the user.")
                return

        # Define static API endpoints
        static_endpoints = [
            ("province", "https://gw.fbr.gov.pk/pdi/v1/provinces", "stateProvinceCode", "stateProvinceDesc"),
            ("doctype", "https://gw.fbr.gov.pk/pdi/v1/doctypecode", "docTypeId", "docDescription"),
            ("hscode", "https://gw.fbr.gov.pk/pdi/v1/itemdesccode", "hS_CODE", "description"),
            ("uom", "https://gw.fbr.gov.pk/pdi/v1/uom", "uoM_ID", "description"),
            ("sale_type", "https://gw.fbr.gov.pk/pdi/v1/transtypecode", "transactioN_TYPE_ID", "transactioN_DESC"),
            ("sro_item_general", "https://gw.fbr.gov.pk/pdi/v1/sroitemcode", "srO_ITEM_ID", "srO_ITEM_DESC"),
        ]

        # Parallelize static API calls
        with ThreadPoolExecutor(max_workers=6) as executor:
            future_to_type = {
                executor.submit(self._call_fbr_api, endpoint, company): (opt_type, code_key, name_key)
                for opt_type, endpoint, code_key, name_key in static_endpoints
                if not self._check_cache_validity(opt_type)
            }

            for future in as_completed(future_to_type):
                opt_type, code_key, name_key = future_to_type[future]
                try:
                    data = future.result()
                    self._update_fbr_options(data, opt_type, code_key, name_key)
                    _logger.info(f"{opt_type.capitalize()} loaded")
                except Exception as e:
                    _logger.error(f"Failed to load {opt_type}: {e}")

        # Handle dependent options (rates and SRO schedules)
                # --- Handle dependent options (Rates & SRO Schedules) ---
        date = fields.Date.today().strftime("%d-%b-%Y")
        origination_supplier = company.fbr_default_origination_supplier or "1"

        # Always get sale_types (either from DB or API)
        sale_types = self.env["fbr.option"].sudo().search([("type", "=", "sale_type")])
        if not sale_types:
            api_sale_types = self._call_fbr_api("https://gw.fbr.gov.pk/pdi/v1/transtypecode", company)
            self._update_fbr_options(api_sale_types, "sale_type", "transactioN_TYPE_ID", "transactioN_DESC")
            sale_types = self.env["fbr.option"].sudo().search([("type", "=", "sale_type")])

        rate_futures = []
        sro_futures = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            # Fetch rates for each sale type
            for sale in sale_types:
                rate_url = f"https://gw.fbr.gov.pk/pdi/v2/SaleTypeToRate?date={date}&transTypeId={sale.code}&originationSupplier={origination_supplier}"
                rate_futures.append(executor.submit(self._call_fbr_api, rate_url, company))

            # Process rate results & fetch SRO schedules
            for future in as_completed(rate_futures):
                rates = future.result() or []
                self._update_fbr_options(rates, "rate", "ratE_ID", "ratE_DESC")
                for rate in rates:
                    rate_id = rate.get("ratE_ID")
                    if not rate_id:
                        continue
                    sro_url = f"https://gw.fbr.gov.pk/pdi/v1/SroSchedule?rate_id={rate_id}&date={date}&origination_supplier_csv={origination_supplier}"
                    sro_data = self._call_fbr_api(sro_url, company)
                    if not sro_data:  # 404 or empty response
                        _logger.debug(f"No SRO schedule found for rate_id={rate_id}")
                        continue
                    self._update_fbr_options(sro_data, "sro", "srO_ID", "srO_DESC")
            # Process SRO schedules
            for future in as_completed(sro_futures):
                sros = future.result()
                self._update_fbr_options(sros, "sro", "srO_ID", "srO_DESC")


        _logger.info("All static and dependent options loaded successfully!")

    def action_load_fbr_options(self):
        _logger.info("Manual load button clicked.")
        self.with_user(self.env.user.id).load_fbr_static_options()  # Ensure correct user context
        return {
            'effect': {
                'fadeout': 'slow',
                'message': 'FBR options loaded successfully!',
                'type': 'rainbow_man',
            }
        }