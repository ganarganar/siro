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

    'depends': ['payment', 'bit_late_payment_penalty'],

    'data': [
        # 'security/ir.model.access.csv',
        'views/siro_form.xml',
        'views/payment_views.xml',
        'views/siro_payment_requests.xml',
        'data/payment_acquirer_data.xml',
    ],

}
