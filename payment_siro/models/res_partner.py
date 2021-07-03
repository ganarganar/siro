from odoo import fields, models, api
import re


class ResPartner(models.Model):

    _inherit = 'res.partner'

    roela_ident = fields.Char(
        'Roela identification',
        compute='_compute_roela_ident',
        inverse='_inverse_dummy',
        store=True
    )

    @api.depends('main_id_number')
    def _compute_roela_ident(self):
        for res in self:
            if res.main_id_number:
                res.roela_ident = re.findall("\d+", res.main_id_number)[0] 
            else:
                res.roela_ident = False                

    def _inverse_dummy(self):
        return

