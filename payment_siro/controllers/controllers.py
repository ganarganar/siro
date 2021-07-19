# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class PaymentSiro(http.Controller):

    @http.route('/payment_siro/ok', auth='public', website=True)
    def btn_ok(self, **kw):
        values = {}
        reference = kw.get('IdReferenciaOperacion', False)
        result = kw.get('IdResultado', False)
            
        if reference and result:
            payment = request.env['payment.transaction'].sudo().search([
                ('reference', '=', reference), ('state', '=', 'authorized')])
            if payment:
                try:
                    payment.btn_process_payment_info(result)
                    values['payment'] = payment
                    return request.render("payment_siro.siro_ok", values)

                except Exception as e:
                    return request.render("payment_siro.siro_error", values)
        return request.render("payment_siro.siro_ok", values)

    @http.route('/payment_siro/error', auth='public', website=True)
    def btn_Error(self, **kw):
        values = {}

        reference = kw.get('IdReferenciaOperacion', False)
        result = kw.get('IdResultado', False)
        
        if reference and result:
            payment = request.env['payment.transaction'].sudo().search([
                ('reference', '=', reference)])
            if payment:
                payment.siro_btn_s2s_void_transaction()
                values['payment'] = payment

        return request.render("payment_siro.siro_error", values)
