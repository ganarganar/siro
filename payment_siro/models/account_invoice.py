
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
from uuid import uuid4
import requests
import re

import logging
_logger = logging.getLogger(__name__)


class AccountInvoice(models.Model):

    _inherit = "account.invoice"

    add_payment_onpost = fields.Boolean(
        string='Add payment on post',
    )

    """def post(self):
        res = self.post()

        for inv in self:
            subscription_id = inv.invoice_line_ids.mapped('subscription_id')
            if len(subscription_id) and inv.add_payment_onpost:
                subscription = subscription_id[0]
                payment_token = subscription.payment_token_id
                if payment_token:
                    tx = subscription._do_payment(payment_token, inv, two_steps_sec=False)[0]

        return res
    """

    # online payments
    def action_add_siro_btn(self, two_steps_sec=True):
        self.ensure_one()
        tx_obj = self.env['payment.transaction']
        reference = str(uuid4())
        payment_method = self.env.ref('payment_siro.payment_acquirer_siro_btn')
        off_session = self.env.context.get('off_session', True)
        payment_token = self.partner_id.payment_token_ids.filtered(lambda x: x.acquirer_id.provider == 'siro_btn')

        values = {
                'amount': self.amount_total,
                'acquirer_id': payment_method.id,
                'type': 'server2server',
                'currency_id': self.currency_id.id,
                'reference': reference,
                'payment_token_id': payment_token.id,
                'partner_id': self.partner_id.id,
                'partner_country_id': self.partner_id.country_id.id,
                'invoice_ids': [(6, 0, [self.id])],
                'callback_model_id': self.env['ir.model'].sudo().search([('model', '=', self._name)], limit=1).id,
                'callback_res_id': self.id,
                'callback_method': 'reconcile_pending_transaction' if off_session else '_reconcile_and_send_mail',
                'return_url': '/my/invoices/%s' % (self.id),
            }

        tx = tx_obj.create(values)
        tx.create_siro_btn()
        baseurl = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        payment_secure = {'3d_secure': two_steps_sec,
                          'accept_url': baseurl + '/my/invoices/%s/payment/%s/accept/' % (self.id, tx.id),
                          'decline_url': baseurl + '/my/invoices/%s/payment/%s/decline/' % (self.id, tx.id),
                          'exception_url': baseurl + '/my/invoices/%s/payment/%s/exception/' % (self.id, tx.id),
                              }
        tx.with_context(off_session=off_session).s2s_do_transaction(**payment_secure)

        return tx

    def action_add_siro(self, two_steps_sec=True):
        self.ensure_one()
        payment_token = self.partner_id.payment_token_ids.filtered(lambda x: x.acquirer_id.provider == 'siro')
        if not len(payment_token):
            raise UserError(_('No hay metodo de pago siro para el cliente'))

        if payment_token.siro_requests:
            invoice = self
            tx_obj = self.env['payment.transaction']
            reference = "SUB%s-%s" % (self.id, datetime.now().strftime('%y%m%d_%H%M%S'))
            off_session = self.env.context.get('off_session', True)
            values = {
                'amount': invoice.amount_total,
                'acquirer_id': payment_token.acquirer_id.id,
                'type': 'server2server',
                'currency_id': invoice.currency_id.id,
                'reference': reference,
                'payment_token_id': payment_token.id,
                'partner_id': self.partner_id.id,
                'partner_country_id': self.partner_id.country_id.id,
                'invoice_ids': [(6, 0, [invoice.id])],
                'callback_model_id': self.env['ir.model'].sudo().search([('model', '=', self._name)], limit=1).id,
                'callback_res_id': self.id,
                'callback_method': 'reconcile_pending_transaction' if off_session else '_reconcile_and_send_mail',
                'return_url': '/my/invoices/%s' % (self.id),
            }

            tx = tx_obj.create(values)

            baseurl = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            payment_secure = {'3d_secure': two_steps_sec,
                              'accept_url': baseurl + '/my/invoices/%s/payment/%s/accept/' % (self.id, tx.id),
                              'decline_url': baseurl + '/my/invoices/%s/payment/%s/decline/' % (self.id, tx.id),
                              'exception_url': baseurl + '/my/invoices/%s/payment/%s/exception/' % (self.id, tx.id),
                              }
            tx.with_context(off_session=off_session).s2s_do_transaction(**payment_secure)

        return tx

    @api.multi
    def reconcile_pending_transaction(self, tx, invoice=False):
        self.ensure_one()
        if not invoice:
            invoice = self
        if tx.state in ['done', 'authorized']:
            invoice.write({'reference': tx.reference, 'name': tx.reference})
