
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

    def get_auth_url(self):
        self.ensure_one()
        if self.state == 'enabled':
            return PROD_AUTH_API_URL
        elif self.state == 'test':
            return TEST_AUTH_API_URL
        else:
            raise UserError(_("Siro is disabled"))

    def get_api_siro_url(self):
        self.ensure_one()
        if self.state == 'enabled':
            return PROD_API_SIRO_URL
        elif self.state == 'test':
            return TEST_API_SIRO_URL
        else:
            raise UserError(_("Siro is disabled"))

    def siro_get_token(self):
        self.ensure_one()
        if self.siro_token_expires < fields.Datetime.now():
            return self.token
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
            ('siro_transactions_id', '=', False),
            ('acquirer_id', '=', self.id),
        ])
        if len(transaction_ids):
            requests = self.env['siro.payment.requests'].create(
                {
                    'acquirer_id': self.id,
                    'transaction_ids': [(6, 0, transaction_ids.ids)],
                }
            )
            self.env.cr.commit()
            requests.send_to_process()


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
         ('send', 'send}'),
         ('process', 'process}'),
         ('done', 'done}'),
         ('cancel', 'cancel}'), ],
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
            seq_expiration = int(
                transaction.amount * transaction.company_id.coefficient_2_expiration * 10)
            third_expiration = int(
                transaction.amount * transaction.company_id.coefficient_3_expiration * 10)
            res += self.parce_text_line([
                ('Reg code', 'fix', '5'),
                ('Reference', 'plot', [
                    ('partner id', '{:0>9d}', transaction.vat_number),
                    ('roela_code', '{:0>10d}',
                     transaction.company_id.roela_code),
                ]
                ),
                ('Factura', 'plot', [
                    ('partner id', '{:0>15d}', transaction.invoice_id.name),
                    ('Concept', 'fix', '0'),
                    ('mes Factura', 'DDMM', transaction.invoice_id.date),
                ]
                ),
                ('cod moneda', 'fix', '0'),
                ('vencimiento', 'AAAAMMDD',
                 transaction.invoice_id.invoice_date_due),
                ('monto', '{:0>11d}', int(transaction.amount * 10)),
                ('seg vencimiento', 'AAAAMMDD', transaction.invoice_id.invoice_date_due +
                 timedelta(days=transaction.company_id.days_2_expiration)),
                ('monto seg vencimiento', '{:0>11d}', seq_expiration),
                ('ter vencimiento', 'AAAAMMDD', transaction.invoice_id.invoice_date_due +
                    timedelta(days=transaction.company_id.days_3_expiration)),
                ('monto ter vencimiento', '{:0>11d}', third_expiration),
                ('filler', '{:0>19d}', 0),
                ('Reference', 'plot', [
                    ('partner id', '{:0>9d}', transaction.vat_number),
                    ('roela_code', '{:0>10d}',
                     transaction.company_id.roela_code),
                ]
                ),
                ('tiket ', 'plot', [
                    ('ente', '{: >15d}', re.sub(
                        '[\W_]+', '', transaction.company_id.name)[:15])
                    ('concepto', '{: >25d}',  re.sub(
                        '[\W_]+', '', transaction.siro_concept)[:25])
                ]),
                ('pantalla', '{: >15d}', re.sub(
                    '[\W_]+', '', transaction.company_id.name)[:15])

                ('codigo barra', 'get_vd', [
                    ('primer dv', 'get_vd',
                        [
                            ('emp', 'fix', '0447'),
                            ('concepto', 'fix', '3'),
                            ('partner id', '{:0>9d}', transaction.vat_number),
                            ('vencimiento', 'AAAAMMDD',
                             transaction.invoice_id.invoice_date_due),
                            ('monto', '{:0>7d}', int(transaction.amount * 10)),
                            ('dias 2', '{:0>2d}',
                             transaction.company_id.days_2_expiration),
                            ('monto 2', '{:0>7d}', seq_expiration),
                            ('dias 3', '{:0>2d}',
                             transaction.company_id.days__expiration),
                            ('monto 2', '{:0>7d}', seq_expiration),
                            ('roela_code', '{:0>10d}',
                             transaction.company_id.roela_code),
                        ]
                     )
                ]),
                ('filler', '{:0>19d}', 0),
            ])
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
        def get_vd(self, string):
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

            return vf

        res = ''

        for item in plot:
            if item[1] == 'fix':
                res += item[2]
            elif item[1] == 'AAAAMMDD':
                res += item[2].strftime("%Y%m%d")
            elif item[1] == 'MMDD':
                res += item[2].strftime("%m%d")
            elif item[1] == 'df':
                to_verify = self.parce_text_line(item[2])
                res += to_verify + get_vd(to_verify)
            elif item[1] == 'plot':
                res += self.parce_text_line(item[2])
            else:
                res += item[2].format(item[0])

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

    siro_transactions_id = fields.Many2one(
        'siro.payment.requests',
        string='Siro request',
    )

    siro_requests = fields.Boolean(
        string='SIRO requests',
    )

    siro_payment_button = fields.Boolean(
        string='SIRO payment button',
    )
    siro_concept = fields.Char(
        string='Concept',
    )

    invoice_id = fields.Many2one(
        'account.move',
        string='Invoice',
        domain=[('type', '=', 'out_invoice')]
    )
