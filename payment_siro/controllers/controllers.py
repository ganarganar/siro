# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class PaymentSiro(http.Controller):

    @http.route('/payment_siro/ok', auth='public', website=True)
    def btn_ok(self, **kw):

        reference = kw.get('IdReferenciaOperacion', False)
        result = kw.get('IdResultado', False)
        
        if reference and result:
            payment = request.env['payment.transaction'].sudo().search([
                ('reference', '=', reference)])
            if payment:
                payment.btn_process_payment_info(result)
        # https://ganargan.ar/payment_siro/error/?IdResultado=f676888d-8427-4cb5-a459-404537484336&IdReferenciaOperacion=28178c06-a428-4934-8c98-72f4af62b97d&Error%20al%20generar%20la%20operaci%c3%b3n:%20El%20tiempo%20de%20vida%20del%20pago%20ha%20expirado

        return 'OK'

    @http.route('/payment_siro/error', auth='public', website=True)
    def btn_Error(self, **kw):

        reference = kw.get('IdReferenciaOperacion', False)
        result = kw.get('IdResultado', False)
        
        if reference and result:
            payment = request.env['payment.transaction'].sudo().search([
                ('reference', '=', reference)])
            if payment:
                payment.btn_process_payment_info(result)
        return 'Error'
