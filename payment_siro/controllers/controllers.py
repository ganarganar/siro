# -*- coding: utf-8 -*-
# from odoo import http


# class PaymentSiro(http.Controller):
#     @http.route('/payment_siro/payment_siro/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/payment_siro/payment_siro/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('payment_siro.listing', {
#             'root': '/payment_siro/payment_siro',
#             'objects': http.request.env['payment_siro.payment_siro'].search([]),
#         })

#     @http.route('/payment_siro/payment_siro/objects/<model("payment_siro.payment_siro"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('payment_siro.object', {
#             'object': obj
#         })
