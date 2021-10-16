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
    siro_payment_token_count = fields.Integer('Count Payment Token', compute='_siro_compute_payment_token_count')

    @api.depends('payment_token_ids')
    def _siro_compute_payment_token_count(self):
        payment_data = self.env['payment.token'].read_group([
            ('partner_id', 'in', self.ids), ('acquirer_id.provider', '=', 'siro')], ['partner_id'], ['partner_id'])
        mapped_data = dict([(payment['partner_id'][0], payment['partner_id_count']) for payment in payment_data])
        for partner in self:
            partner.siro_payment_token_count = mapped_data.get(partner.id, 0)

    @api.depends('main_id_number')
    def _compute_roela_ident(self):
        for res in self:
            if res.main_id_number:
                roela_ident = re.findall("\d+", res.main_id_number)[0]
                #es cuit
                if len(roela_ident) > 9:
                    res.roela_ident = roela_ident[2:9]
                else:
                    res.roela_ident = roela_ident

            else:
                res.roela_ident = False

    def _inverse_dummy(self):
        return

    def add_siro_payment_token(self):
        for res in self:
            payment_token_id = res.payment_token_ids.filtered(
                lambda x: x.acquirer_id.provider == 'siro')
            if not len(payment_token_id):
                payment_siro = self.env['payment.acquirer'].search(
                    [('provider', '=', 'siro')], limit=1)
                if len(payment_siro):
                    self.env['payment.token'].create({
                        'name': 'Pago mediante Siro',
                        'partner_id': res.id,
                        'acquirer_id': payment_siro.id,
                        'acquirer_ref': res.roela_ident,
                        'siro_requests': True,
                        'siro_payment_button': True,
                    })
