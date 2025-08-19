from . import models

from odoo import api, SUPERUSER_ID
import logging
_logger = logging.getLogger(__name__)


def _compute_fbr_rates_for_existing_products(env):
    """ Compute FBR rates for all existing products """
    # env = api.Environment(cr, SUPERUSER_ID, {})
    products = env['product.template'].search([])
    products._compute_fbr_rate_id()
    _logger.info("Computed FBR rates for %s existing products", len(products))
    
def load_fbr_data_after_install(env):
    """ Compute FBR rates for all existing products """
    # env = api.Environment(cr, SUPERUSER_ID, {})
    products = env['product.template'].search([])
    products.load_fbr_static_options()
    _logger.info("Computed FBR options", len(products))