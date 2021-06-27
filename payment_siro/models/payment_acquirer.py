
from odoo import fields, models, _
from odoo.exceptions import UserError
from datetime import datetime,  timedelta
import requests
import re

import logging
_logger = logging.getLogger(__name__)

TEST_AUTH_API_URL = "https://apisesionhomologa.bancoroela.com.ar:49221/auth/Sesion"
PROD_AUTH_API_URL = "https://apisesionhomologa.bancoroela.com.ar:49221/auth/Sesion"

TEST_API_SIRO_URL = "https://apisirohomologa.bancoroela.com.ar:49220"
PROD_API_SIRO_URL = "https://apisirohomologa.bancoroela.com.ar:49220"


class PaymentAcquirer(models.Model):

    _inherit = "payment.acquirer"

    provider = fields.Selection(selection_add=[('siro', 'SIRO')])
    siro_user = fields.Char(
        string='Siro User',
    )
    siro_password = fields.Char(
        string='Siro Pass',
    )
    siro_token = fields.Text(
        string='Siro token',
    )
    siro_token_expires = fields.Datetime(
        string='Siro token expires',
    )
    roela_code = fields.Integer(
        string='Roela Identification',
    )

    def get_auth_url(self):
        self.ensure_one()

        if self.environment == 'prod':
            return PROD_AUTH_API_URL
        elif self.environment == 'test':
            return TEST_AUTH_API_URL
        else:
            raise UserError(_("Siro is disabled"))

    def get_api_siro_url(self):
        self.ensure_one()
        if self.environment == 'enabled':
            return PROD_API_SIRO_URL
        elif self.environment == 'test':
            return TEST_API_SIRO_URL
        else:
            raise UserError(_("Siro is disabled"))

    def siro_get_token(self):
        self.ensure_one()
        if self.siro_token and self.siro_token_expires < datetime.now():
            return self.siro_token
        else:
            api_url = self.get_auth_url()

            request_data = {
                "Usuario": self.siro_user,
                "Password": self.siro_password
            }

            response = requests.post(api_url, json=request_data)
            if response.status_code == 200:
                res = response.json()
                self.siro_token = res['access_token']
                self.siro_token_expires = datetime.now(
                ) + timedelta(seconds=res['expires_in'] - 20)
                return res['access_token']
            else:
                raise UserError(_("Siro can't login"))

    def siro_send_process(self):
        self.ensure_one()
        transaction_ids = self.env['payment.transaction'].search([
            ('siro_requests_id', '=', False),
            ('acquirer_id', '=', self.id),
        ])
        _logger.info(transaction_ids)
        if len(transaction_ids):
            requests = self.env['siro.payment.requests'].create(
                {
                    'acquirer_id': self.id,
                    'transaction_ids': [(6, 0, transaction_ids.ids)],
                }
            )
            requests.create_register()
            #self.env.cr.commit()

            #requests.send_to_process()


class SiroPaymentRequest(models.Model):
    _name = 'siro.payment.requests'
    _description = 'SIRO payment requests'

    name = fields.Char(
        string='Trasaction number',
        default='/'
    )

    acquirer_id = fields.Many2one(
        'payment.acquirer',
        string='Payment acquirer',
    )
    data = fields.Text(
        string='Data',
    )
    transaction_ids = fields.One2many(
        'payment.transaction',
        'siro_requests_id',
        string='Transactions',
    )
    log = fields.Text(
        string='Data Log',
    )
    state = fields.Selection(
        [('draft', 'draft'),
         ('send', 'send'),
         ('process', 'process'),
         ('done', 'done'),
         ('cancel', 'cancel'), ],
        string='State',
        default='draft'
    )

    def send_to_process(self):
        self.ensure_one()
        self.create_register()
        access_token = self.acquirer_id.siro_get_token()

        api_url = self.acquirer_id.get_api_siro_url() + "/siro/Pagos"
        request_data = {
            "base_pagos": "string",
            "confirmar_automaticamente": True
        }
        headers = {"Authorization": "Bearer %s" % access_token}
        response = requests.post(api_url, headers=headers, json=request_data)
        if response.status_code == 200:
            stringProcess = response.json()
            self.state = 'send'
            self.name = stringProcess['nro_transaccion']
        else:
            print(response.content)

    def create_register(self):
        self.ensure_one()
        # esto podria armarlo como un string
        # pero el debug se volveria complicado
        res = ''
        res += self.parce_text_line([
            ('Reg code', 'fix', '0'),
            ('banelco code', 'fix', '400'),
            ('company code', 'fix', '0000'),
            ('date', 'AAAAMMDD', fields.Date.today()),
            ('filler', '{:0>12d}', 0),
        ])
        res += '\n'
        total = 0
        count_items = 0
        for transaction in self.transaction_ids:
            total += int(transaction.amount * 10)
            count_items += 1

            expiration_days = 20
            date_expiration = fields.Date.from_string(transaction.invoice_id.date_due)
            second_expiration = int(
                transaction.invoice_id.amount_total_with_penalty * 10)
            third_expiration = second_expiration
            date_second_expiration = date_expiration + timedelta(days=expiration_days)
            date_third_expiration = date_second_expiration
            company_id = self.env.user.company_id

            plot = [
                ('Reg code', 'fix', '5'),
                ('Reference', 'plot', [
                    ('partner id', '{:0>9d}', int(transaction.partner_id.main_id_number)),
                    ('roela_code', '{:0>10d}',
                     transaction.acquirer_id.roela_code),
                ]
                ),
                ('Factura', 'plot', [
                    ('Invoice', '{:0>15d}', 4458754),#transaction.invoice_id.name),
                    ('Concept', 'fix', '0'),
                    ('mes Factura', 'DDMM', transaction.invoice_id.date),
                ]
                ),
                ('cod moneda', 'fix', '0'),
                ('vencimiento', 'AAAAMMDD', date_expiration),
                ('monto', '{:0>11d}', int(transaction.amount * 10)),
                ('seg vencimiento', 'AAAAMMDD', date_second_expiration),
                ('monto seg vencimiento', '{:0>11d}', second_expiration),
                ('ter vencimiento', 'AAAAMMDD', date_third_expiration),
                ('monto ter vencimiento', '{:0>11d}', third_expiration),
                ('filler', '{:0>19d}', 0),
                ('Reference', 'plot', [
                    ('partner id', '{:0>9d}', int(transaction.partner_id.main_id_number)),
                    ('roela_code', '{:0>10d}',
                     transaction.acquirer_id.roela_code),
                ]
                ),

                ('tiket ', 'plot', [
                    ('ente', '{: >15}', re.sub('[\W_]+', '', company_id.name)[:15]),
                    ('concepto', '{: >25}',  re.sub('[\W_]+', '', transaction.payment_token_id.name)[:25])
                ]),
                ('pantalla', '{: >15}', re.sub(
                    '[\W_]+', '', company_id.name)[:15]),

                ('codigo barra', 'get_vd', [
                    ('primer dv', 'get_vd',
                        [
                            ('emp', 'fix', '0447'),
                            ('concepto', 'fix', '3'),
                            ('partner id', '{:0>9d}', int(transaction.partner_id.main_id_number)),
                            ('vencimiento', 'AAAAMMDD', date_expiration),
                            ('monto', '{:0>7d}', int(transaction.amount * 10)),
                            ('dias 2', '{:0>2d}', expiration_days),
                            ('monto 2', '{:0>7d}', second_expiration),
                            ('dias 3', '{:0>2d}', expiration_days),
                            ('monto 3', '{:0>7d}', third_expiration),
                            ('roela_code', '{:0>10d}', transaction.acquirer_id.roela_code),
                        ]
                     )
                ]),
                ('filler', '{:0>19d}', 0),
            ]
            res += self.parce_text_line(plot)

            res += '\n'

        res += self.parce_text_line([
            ('Reg code', 'fix', '9'),
            ('banelco code', 'fix', '400'),
            ('company code', 'fix', '0000'),
            ('date', 'AAAAMMDD', fields.Date.today()),
            ('cant', '{:0>7d}', count_items),
            ('filler', '{:0>7d}', 0),
            ('total', '{:0>11d}', total * 10),
            ('filler', '{:0>239d}', 0),

        ])
        self.data = res
        return res

    def parce_text_line(self, plot):
        def get_vd(string):
            vf = int(string[0])
            base = [3, 5, 7, 9]
            base_pos = 0

            for letter in string[1:]:
                vf += int(letter) * base[base_pos]
                base_pos += 1
                if base_pos == len(base):
                    base_pos = 0
                vf = vf / 2.0
                vf = int(vf) % 10.0
            return str(int(vf))

        res = ''
        for item in plot:
            if item[1] == 'fix':
                res += item[2]
            elif item[1] == 'AAAAMMDD':
                res += item[2].strftime("%Y%m%d")
            elif item[1] == 'MMDD':
                res += item[2].strftime("%m%d")
            elif item[1] == 'get_vd':

                to_verify = self.parce_text_line(item[2])
                res += to_verify + get_vd(to_verify)
            elif item[1] == 'plot':
                res += self.parce_text_line(item[2])
            else:
                res += item[1].format(item[2])

        return res
"""
{
  "cantidad_registros_correctos": 0,
  "cantidad_registros_erroneos": 0,
  "cantidad_registros_procesados": 0,
  "confirmar_automaticamente": true,
  "error_descripcion": "string",
  "errores": [
    null
  ],
  "estado": "string",
  "fecha_envio": "2021-06-12T23:00:41.696Z",
  "fecha_proceso": "2021-06-12T23:00:41.696Z",
  "fecha_registro": "2021-06-12T23:00:41.696Z",
  "nro_transaccion": 0,
  "registro": "string",
  "total_primer_vencimiento": 0,
  "total_segundo_vencimiento": 0,
  "total_tercer_vencimiento": 0,
  "usuario_id": 0,
  "via_ingreso": "string"
}"""


class paymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    siro_requests = fields.Boolean(
        string='SIRO requests',
        related='payment_token_id.siro_requests'
    )
    siro_payment_button = fields.Boolean(
        string='SIRO payment button',
        related='payment_token_id.siro_payment_button'
    )
    siro_requests_id = fields.Many2one(
        'siro.payment.requests',
        string='Siro request',
    )
    siro_concept = fields.Char(
        string='Concept',
    )

    invoice_id = fields.Many2one(
        'account.invoice',
        string='Invoice',
        domain=[('type', '=', 'out_invoice')]
    )


class paymentToken(models.Model):

    _inherit = 'payment.token'

    provider = fields.Char(
        string='provider',
        realted='acquirer_id.provider',
    )

    siro_requests = fields.Boolean(
        string='SIRO requests',
    )
    siro_payment_button = fields.Boolean(
        string='SIRO payment button',
    )
