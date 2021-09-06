from odoo import fields, models


class ResCompany(models.Model):

    _inherit = 'res.company'

    roela_code = fields.Char(
        string='Roela Identification',
    )

    days_2_expiration = fields.Integer(
        string='days to second expiration',
        default=20
    )

    days_3_expiration = fields.Integer(
        string='days to third expiration',
        default=20
    )
    