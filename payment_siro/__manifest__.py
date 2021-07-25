# -*- coding: utf-8 -*-
{
    'name': "Payment siro",

    'summary': "Servicio Integral de Recaudación Banco Roela",

    'description': """
         SIRO es el Servicio Integral de Recaudación de Banco Roela, que cuenta con todos los medios de pago, 
         de fácil implementación y rendición centralizada de las cobranzas. 
    """,

    'author': "Filoquin",
    'website': "http://ganargan.ar",

    'category': 'Payment',
    'version': '12.0.0.0.1',

    'depends': ['payment', 'l10n_ar_account', 'bit_late_payment_penalty', 'sale_subscription'],

    'data': [
        'security/ir.model.access.csv',
        'views/templates.xml',
        'views/siro_form.xml',
        'views/payment_views.xml',
        'views/siro_payment_requests.xml',
        'views/res_partner.xml',
        'views/account_invoice.xml',
        'views/sale_subscription.xml',
        'views/ir_cron.xml',
        'data/payment_acquirer_data.xml',
    ],

}
