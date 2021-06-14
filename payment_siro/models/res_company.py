from odoo import fields, models


class ResCompany(models.Model):

    _inherit = 'res.company'

    roela_code = fields.Char(
        string='Roela Identification',
    )

    days_2_expiration = fields.Integer(
        string='days to second expiration',
    )

    coefficient_2_expiration = fields.Float(
        string='coefficient for second expiration',
        default=1.0
    )

    days_3_expiration = fields.Integer(
        string='days to third expiration',
    )
    coefficient_3_expiration = fields.Float(
        string='coefficient for third expiration',
        default=1.0
    )
