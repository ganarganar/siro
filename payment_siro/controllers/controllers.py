# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

import logging
_logger = logging.getLogger(__name__)


class PaymentSiro(http.Controller):

    @http.route(['/payment_siro/ok', '/payment_siro/error'], auth='public', website=True)
    def payment_siro(self, **kw):
        values = {}
        reference = kw.get('IdReferenciaOperacion', False)
        result = kw.get('IdResultado', False)


        if reference and result:
            payment = request.env['payment.transaction'].sudo().search([
                ('reference', '=', reference)])
            if payment:
                values['payment'] = payment
                try:    
                    result = payment.btn_process_payment_info(result)

                    values['result'] = result 
                    if result['PagoExitoso']:
                        return request.render("payment_siro.siro_ok", values)
                    else: 
                        payment.siro_btn_s2s_void_transaction()
                        return request.render("payment_siro.siro_error", values)

                except Exception as e:
                    values['payment'] = payment
                    return request.render("payment_siro.siro_error", values)

        values['payment'] = {}

        return request.render("payment_siro.siro_error", values)

    @http.route(['/payment_siro/retry'], auth='public', website=True)
    def payment_siro_retry(self, access_token, **kw):
        values = {}

        invoice_id = request.env['account.invoice'].search([
            ('access_token', '=', access_token),
            ('state', '=', 'open')
        ])
        if invoice_id:
            if invoice_id.state == 'paid':
                values['payment'] = {}
                return request.render("payment_siro.siro_ok", values)

            invoice_id.action_add_siro_btn()
            siro_btn_url = invoice_id.sudo().action_siro_btn_get_url()[0]
            return request.redirect(siro_btn_url)

        return 'fail'

    @http.route(['/payment_siro/start'], auth='public', website=True)
    def payment_siro_start(self, access_token, **kw):
        values = {}
        invoice_id = request.env['account.invoice'].search([
            ('access_token', '=', access_token),
            ('state', '=', 'open')
        ])
        if invoice_id:
            # Si la factura esta pagada enviar el template siro_ok
            if invoice_id.state == 'paid':
                values['payment'] = {}
                return request.render("payment_siro.siro_ok", values)

            siro_btn_url = invoice_id.sudo().action_siro_btn_get_url()[0]
            return request.redirect(siro_btn_url)
        return 'fail'        