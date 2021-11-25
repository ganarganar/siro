from odoo import fields, models


class ResCompany(models.Model):

    _inherit = 'res.company'

    roela_code = fields.Char(
        string='Roela Identification',
    )
    days_expiration = fields.Integer(
        string='Dias para el 1 vencimiento',
        default=3

    )

    days_2_expiration = fields.Integer(
        string='Dias para el 2 vencimiento',
        default=20
    )

    days_3_expiration = fields.Integer(
        string='Dias para el 3 vencimiento',
        default=20
    )
    