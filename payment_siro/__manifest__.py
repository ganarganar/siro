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
    'version': '13.0.0.0.1',

    'depends': ['payment'],

    'data': [
        # 'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
    ],

}
