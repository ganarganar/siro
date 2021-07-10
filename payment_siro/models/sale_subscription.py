
from odoo import fields, models, api, _

import logging
_logger = logging.getLogger(__name__)


class SaleSubscription(models.Model):

    _inherit = "sale.subscription"

    def _prepare_invoice_data(self):
        self.ensure_one()
        res = super(SaleSubscription, self)._prepare_invoice_data()
        if self.template_id.payment_mode == 'draft_invoice' and len(self.payment_token_id):
            res['add_payment_onpost'] = True
        return res
