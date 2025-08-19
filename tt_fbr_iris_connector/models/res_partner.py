from odoo import models, fields, api
import requests
import logging

_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _inherit = 'res.partner'

    ntn = fields.Char(
        string='NTN',
        help='National Tax Number of the partner'
    )
    region = fields.Selection(
        selection=[
            ('Azad Jammu and Kashmir', 'Azad Jammu and Kashmir'),
            ('Balochistan', 'Balochistan'),
            ('Capital Territory', 'Capital Territory'),
            ('FATA/PATA', 'FATA/PATA'),
            ('Gilgit Baltistan', 'Gilgit Baltistan'),
            ('Khyber Pakhtunkhwa', 'Khyber Pakhtunkhwa'),
            ('Punjab', 'Punjab'),
            ('Sindh', 'Sindh'),
        ],
        string='Region',
        help='Select the region associated with this partner.',
    )
    fbr_address = fields.Char(
        string='FBR Address',
        help='Address registered with the Federal Board of Revenue (FBR).'
    )
    fbr_registration_type = fields.Selection(
        selection=[
            ('Unregistered', 'Unregistered'),
            ('Registered', 'Registered'),
        ],
        string='FBR Registration Type',
        help='Type of registration with the Federal Board of Revenue (FBR).',readonly=True
    )
    def check_fbr_registration(self):
        token = self.env.company.fbr_bearer_token
        if not token:
            _logger.warning("⚠️ FBR Bearer Token not found in company settings.")
            return []
        url = "https://gw.fbr.gov.pk/dist/v1/Get_Reg_Type"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        for partner in self:
            if not partner.ntn:
                _logger.warning(f"Partner {partner.name} has no NTN to check with FBR.")
                continue
            
            payload = {"Registration_No": partner.ntn}
            try:
                _logger.info(f"Calling FBR API for NTN: {partner.ntn}")
                response = requests.post(url, json=payload, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    reg_type = data.get("REGISTRATION_TYPE", "").lower()
                    if reg_type == "registered":
                        partner.fbr_registration_type = 'Registered'
                    elif reg_type == "unregistered":
                        partner.fbr_registration_type = 'Unregistered'
                    else:
                        partner.fbr_registration_type = False
                    _logger.info(f"Updated FBR registration type for {partner.ntn}: {partner.fbr_registration_type}")
                else:
                    _logger.error(f"FBR API call failed with code {response.status_code}: {response.text}")
            except Exception as e:
                _logger.exception(f"Exception during FBR API call for NTN {partner.ntn}: {e}")

