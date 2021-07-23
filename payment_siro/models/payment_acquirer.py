
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from datetime import datetime,  timedelta
from uuid import uuid4

import requests
import re

import logging
_logger = logging.getLogger(__name__)

# API 
TEST_AUTH_API_URL = "https://apisesionhomologa.bancoroela.com.ar:49221/auth/Sesion"
PROD_AUTH_API_URL = "https://apisesionhomologa.bancoroela.com.ar:49221/auth/Sesion"

TEST_API_SIRO_URL = "https://apisirohomologa.bancoroela.com.ar:49220"
PROD_API_SIRO_URL = "https://apisirohomologa.bancoroela.com.ar:49220"

# BOTON 
TEST_BTN_API_URL = "https://srvwebhomologa.bancoroela.com.ar:44443/"
PROD_BTN_API_URL = "https://srvwebhomologa.bancoroela.com.ar:44443/"


class PaymentAcquirer(models.Model):

    _inherit = "payment.acquirer"

    provider = fields.Selection(selection_add=[('siro', 'SIRO'), ('siro_btn', 'SIRO botón de pagos')])
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
    roela_code = fields.Char(
        string='Roela Identification',
    )
    roela_date_from = fields.Date(
        string='roela date from',
        default="2020-12-01"
    )
    roela_date_to = fields.Date(
        string='roela date to',
        default="2020-12-31"
    )

    siro_btn_user = fields.Char(
        string='Siro User',
    )
    siro_btn_password = fields.Char(
        string='Siro Pass',
    )
    siro_btn_token = fields.Text(
        string='Siro token',
    )
    siro_btn_token_expires = fields.Datetime(
        string='Siro token expires',
    )

    def _get_feature_support(self):
        res = super()._get_feature_support()
        res['authorize'].append('siro')
        res['tokenize'].append('siro')
        res['authorize'].append('siro_btn')
        res['tokenize'].append('siro_btn')
        return res

    def test_process(self, test):
        if self.environment != 'test':
            raise UserError(_('Solo se puede usar en modo tests'))
        transaction_ids = self.env['payment.transaction'].search([
            ('state', 'in', ['authorized']),
            ('acquirer_id.provider', '=', 'siro'),
            ('siro_barcode', '!=', False),


        ])
        _logger.info('test OK %s' % transaction_ids)
        for transaction in transaction_ids:
            transaction.amount = transaction.amount
            transaction._set_transaction_done()
            transaction._reconcile_after_transaction_done()

    def list_process(self, date_from=False, date_to=False):

        date_from = '%sT00:00:00.000Z' % self.roela_date_from
        date_to = '%sT23:59:59.999Z' % self.roela_date_to

        access_token = self.siro_get_token()
        api_url = self.get_api_siro_url() + "/siro/Listados/Proceso"
        headers = {"Authorization": "Bearer %s" % access_token}
        request_data = {
            "fecha_desde": date_from,
            "fecha_hasta": date_to,
            "cuit_administrador": "%s" % self.company_id.main_id_number.replace('-', ''),
            "nro_empresa": self.roela_code
        }
        response = requests.post(api_url, headers=headers, json=request_data)

        if response.status_code == 200:
            line_def = self.get_alternate_format_file()
            res = response.json()
            for line in res:
                line_info = self.parce_text_line(line, line_def)
                transaction = self.env['payment.transaction'].search([
                    ('state', 'not in', ['done', 'cancel']),
                    ('acquirer_id.provider', '=', 'siro'),
                    ('siro_barcode', '=', line_info['barcode'])

                ])
                if transaction:
                    _logger.info('payment OK')
                    transaction.amount = line_info['amount']
                    transaction._set_transaction_done()
                    transaction._reconcile_after_transaction_done()
                else:

                    _logger.info('payment ko')
        else:
            raise UserError(response.content)

    @api.model
    def get_alternate_format_file(self):
        return [
            ('payment_date', 'AAAAMMDD', 8),
            ('acreditation_date', 'AAAAMMDD', 8),
            ('first_expiration_date', 'AAAAMMDD', 8),
            ('amount', 'int_to_float', 7, 10),
            ('userid', 'char', 8),
            ('concept', 'char', 1),
            ('barcode', 'char', 56),
            ('chanel', 'char', 3),
        ]

    @api.model
    def get_siro_extended_format_file(self):
        return [
            ('payment_date', 'AAAAMMDD', 8),
            ('acreditation_date', 'AAAAMMDD', 8),
            ('first_expiration_date', 'AAAAMMDD', 8),
            ('amount', 'int_to_float', 7, 10),
            ('userid', 'char', 8),
            ('concept', 'char', 1),
            ('barcode', 'char', 56),
            ('chanel', 'char', 3),
        ]

    @api.model
    def parce_text_line(self, line, line_def):
        cursor = 0
        res = {}
        for item in line_def:
            text = line[cursor:cursor + item[2]]
            if item[1] == 'AAAAMMDD':
                res[item[0]] = fields.Date.to_string(
                    datetime.strptime(text, '%Y%m%d'))
            elif item[1] == 'int_to_float':
                res[item[0]] = int(text) / item[3]
            elif item[1] == 'int':
                res[item[0]] = int(text)
            else:
                res[item[0]] = text

            cursor += item[2]
        return res

    @api.model
    def parce_render_line(self, line):
        pass

    def get_btn_url(self):
        self.ensure_one()

        if self.environment == 'prod':
            return PROD_BTN_API_URL
        elif self.environment == 'test':
            return TEST_BTN_API_URL
        else:
            raise UserError(_("Siro is disabled"))

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

        if self.siro_token and fields.Datetime.from_string(self.siro_token_expires) > datetime.now():
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

    def siro_btn_get_token(self):
        self.ensure_one()

        if self.siro_btn_token and fields.Datetime.from_string(self.siro_btn_token_expires) > datetime.now():
            return self.siro_btn_token
        else:
            api_url = self.get_btn_url() + 'api/Sesion'

            request_data = {
                "Usuario": self.siro_btn_user,
                "Password": self.siro_btn_password
            }

            response = requests.post(api_url, json=request_data)
            if response.status_code == 200:
                res = response.json()
                _logger.info(res)
                self.siro_btn_token = res['access_token']
                self.siro_btn_token_expires = datetime.now(
                ) + timedelta(seconds=res['expires_in'] - 20)
                return res['access_token']
            else:
                _logger.error(response.text)
                raise UserError(_("Button Siro can't login"))


    def siro_send_process(self):
        self.ensure_one()
        transaction_ids = self.env['payment.transaction'].search([
            ('siro_requests_id', '=', False),
            ('acquirer_id', '=', self.id),
        ])
        if len(transaction_ids):
            requests = self.env['siro.payment.requests'].create(
                {
                    'acquirer_id': self.id,
                    'transaction_ids': [(6, 0, transaction_ids.ids)],
                }
            )
            # requests.create_register()
            # self.env.cr.commit()

            requests.send_to_process()


class SiroPaymentRequest(models.Model):
    _name = 'siro.payment.requests'
    _description = 'SIRO payment requests'

    _inherit = ['mail.thread', 'mail.activity.mixin']

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
         ('pending', 'pending'),
         ('process', 'process'),
         ('done', 'done'),
         ('cancel', 'cancel'), ],
        string='State',
        default='draft'
    )

    reg_ok = fields.Integer(
        string='ok',
    )
    reg_ko = fields.Integer(
        string='ko',
    )
    reg_pros = fields.Integer(
        string='pros',
    )
    error_text = fields.Char(
        string='error text',
    )
    first_expiration = fields.Integer(
        string='first expiration',
    )
    second_expiration = fields.Integer(
        string='second expiration',
    )
    thrid_expiration = fields.Integer(
        string='thrid expiration',
    )
    reg_err = fields.Text(
        string='reg_err',
    )

    def send_to_process(self):
        self.ensure_one()
        self.create_register()
        access_token = self.acquirer_id.siro_get_token()

        api_url = self.acquirer_id.get_api_siro_url() + "/siro/Pagos"
        request_data = {
            "base_pagos": self.data,
            "confirmar_automaticamente": True
        }
        headers = {"Authorization": "Bearer %s" % access_token}
        response = requests.post(api_url, headers=headers, json=request_data)
        if response.status_code == 200:
            stringProcess = response.json()
            self.state = 'send'
            self.name = stringProcess['nro_transaccion']
            self.message_post(body=_(
                'requests Send. Transactions number %s ' % stringProcess['nro_transaccion']))

        else:
            self.message_post(body=_('Requests Error.  %r ' %
                                     response.content))
            _logger.info(response.content)

    def check_process(self):
        for req in self:
            access_token = self.acquirer_id.siro_get_token()

            api_url = self.acquirer_id.get_api_siro_url(
            ) + "/siro/Pagos/%s?obtener_informacion_base=false" % req.name

            headers = {"Authorization": "Bearer %s" % access_token}
            response = requests.get(
                api_url, headers=headers)
            if response.status_code == 200:
                res = response.json()

                data = {
                    'reg_ok': res['cantidad_registros_correctos'],
                    'reg_ko': res['cantidad_registros_erroneos'],
                    'reg_pros': res['cantidad_registros_procesados'],
                    'error_text': res['error_descripcion'],
                    'first_expiration': res['total_primer_vencimiento'],
                    'second_expiration': res['total_segundo_vencimiento'],
                    'thrid_expiration': res['total_tercer_vencimiento'],

                }
                if res['estado'] == 'PENDIENTE':
                    data['state'] = 'pending'
                    req.transaction_ids._set_transaction_pending()
                if res['estado'] == 'AUTORIZADO':
                    data['state'] = 'authorized'
                    req.transaction_ids._set_transaction_authorized()

                req.write(data)
                ret_text = ''
                for t in res.keys():
                    ret_text += "%s: %s <br/>\n" % (t, res[t])
                self.message_post(body=_(
                    'requests check. Transaction number %s <br/>\n %s' % (req.name, ret_text)))

            else:
                self.message_post(
                    body=_('Requests Error.  %r ' % response.content))
                _logger.info(response.content)

    def prepare_line_dict(self, transaction):

        # La Factura es obligatoria como id
        # la primer factura es que vale
        if not len(transaction.invoice_ids):
            raise UserError(_('No hat factura en la transaccion %s' % transaction.name ))
        invoice_id = transaction.invoice_ids[0]
        expiration_days = 20
        date_expiration = fields.Date.from_string(invoice_id.date_due)
        second_expiration = int(invoice_id.amount_total_with_penalty * 10)

        third_expiration = second_expiration
        date_second_expiration = date_expiration
        date_third_expiration = date_expiration
        company_id = self.env.user.company_id

        return [
            ('Reg code', 'fix', '5'),
            ('Reference', 'plot', [
                ('partner id', '{:0>9d}', int(
                    transaction.partner_id.roela_ident)),
                ('roela_code', '{:0>10d}',
                 int(transaction.acquirer_id.roela_code)),
            ]
            ),
            ('Factura', 'plot', [
                # transaction.invoice_id.name),
                ('Invoice', '{:0>15d}', 4458754),
                ('Concept', 'fix', '0'),
                ('mes Factura', 'MMAA', invoice_id.date_invoice),
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
                ('partner id', '{:0>9d}', int(
                    transaction.partner_id.roela_ident)),
                ('roela_code', '{:0>10d}',
                 int(transaction.acquirer_id.roela_code)),
            ]
            ),

            ('tiket ', 'plot', [
                ('ente', '{: >15}', re.sub(
                    '[\W_]+', '', company_id.name)[:15]),
                ('concepto', '{: >25}',  re.sub(
                    '[\W_]+', '', transaction.payment_token_id.name)[:25])
            ]),
            ('pantalla', '{: >15}', re.sub(
                '[\W_]+', '', company_id.name)[:15]),

            ('codigo barra', 'get_vd', [
                ('primer dv', 'get_vd',
                    [
                        ('emp', 'fix', '0447'),
                        ('concepto', 'fix', '3'),
                        ('partner id', '{:0>9d}', int(
                            transaction.partner_id.roela_ident)),
                        ('vencimiento', 'AAAAMMDD', date_expiration),
                        ('monto', '{:0>7d}', int(transaction.amount * 10)),
                        ('dias 2', '{:0>2d}', expiration_days),
                        ('monto 2', '{:0>7d}', second_expiration),
                        ('dias 3', '{:0>2d}', expiration_days),
                        ('monto 3', '{:0>7d}', third_expiration),
                        ('roela_code', '{:0>10d}', int(
                            transaction.acquirer_id.roela_code)),
                    ]
                 )
            ]),
            ('filler', '{:0>19d}', 0),
        ]

    def describre_json(self):
        self.create_register()
        res = 'ENCABEZADO<br>'

        res += self.parce_text_line([
            ('Reg code', 'fix', '0'),
            ('banelco code', 'fix', '400'),
            ('company code', 'fix', '0000'),
            ('date', 'AAAAMMDD', fields.Date.today()),
            ('filler', '{:0>12d}', 0),
        ])
        res += '<br/>---------<br/>'
        total = 0
        count_items = 0
        for transaction in self.transaction_ids:
            total += int(transaction.amount * 10)
            count_items += 1
            plot = self.prepare_line_dict(transaction)

            res += self.describe_text_line(plot)
            res += '---------<br/>'
        res += self.describe_text_line([
            ('Reg code', 'fix', '9'),
            ('banelco code', 'fix', '400'),
            ('company code', 'fix', '0000'),
            ('date', 'AAAAMMDD', fields.Date.today()),
            ('cant', '{:0>7d}', count_items),
            ('filler', '{:0>7d}', 0),
            ('total', '{:0>11d}', total * 10),
            ('filler', '{:0>239d}', 0),

        ])
        self.message_post(body=res)

        request_data = {
            "base_pagos": self.data.replace('\n', '<br/>'),
            "confirmar_automaticamente": True
        }

        self.message_post(body=request_data)

    def describe_text_line(self, plot):
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
                res += item[0] + ":" + item[2] + "|<br/>"
            elif item[1] == 'AAAAMMDD':
                res += item[0] + ":" + item[2].strftime("%Y%m%d") + "|<br/>"
            elif item[1] == 'MMAA':
                res += item[0] + ":" + item[2].strftime("%m%y") + "|<br/>"

            elif item[1] == 'MMDD':
                res += item[0] + ":" + item[2].strftime("%m%d") + "|<br/>"
            elif item[1] == 'get_vd':

                to_verify = self.parce_text_line(item[2])
                res += item[0] + ":" + to_verify + get_vd(to_verify) + "|<br/>"
            elif item[1] == 'plot':
                res += item[0] + "<br/>" + \
                    self.describe_text_line(item[2]) + "|<br/>"
            else:
                res += item[0] + ":" + item[1].format(item[2]) + "|<br/>"

        return res

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

            # La Factura es obligatoria como id
            # la primer factura es que vale
            invoice_id = transaction.invoice_ids[0]
            expiration_days = 20
            date_expiration = fields.Date.from_string(invoice_id.date_due)
            second_expiration = int(invoice_id.amount_total_with_penalty * 10)

            third_expiration = second_expiration

            plot = self.prepare_line_dict(transaction)

            res += self.parce_text_line(plot)
            barcode = [('codigo barra', 'get_vd', [
                ('primer dv', 'get_vd',
                        [
                            ('emp', 'fix', '0447'),
                            ('concepto', 'fix', '3'),
                            ('partner id', '{:0>9d}', int(
                                transaction.partner_id.roela_ident)),
                            ('vencimiento', 'AAAAMMDD', date_expiration),
                            ('monto', '{:0>7d}', int(transaction.amount * 10)),
                            ('dias 2', '{:0>2d}', expiration_days),
                            ('monto 2', '{:0>7d}', second_expiration),
                            ('dias 3', '{:0>2d}', expiration_days),
                            ('monto 3', '{:0>7d}', third_expiration),
                            ('roela_code', '{:0>10d}', int(
                                transaction.acquirer_id.roela_code)),
                        ]
                        )
            ])]
            transaction.siro_barcode = self.parce_text_line(barcode)
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
        self.message_post(body=_('requests Prepared'))
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
            elif item[1] == 'MMAA':
                res += item[2].strftime("%m%y")
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
    siro_barcode = fields.Char(
        string='SIRO barcode',
    )
    siro_channel = fields.Char(
        string='SIRO channel',
    )
    siro_btn_reference = fields.Char(
        string='Btn Ref',
    )
    siro_btn_url = fields.Char(
        string='Url',
    )


    def siro_btn_prepare_request(self): 
        baseurl = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        baseurl = 'http://ganargan.ar'
        rqst = {
          "nro_cliente_empresa": self.acquirer_id.roela_code,
          "nro_comprobante": re.sub('[\W_]+', '',self.invoice_ids[0].display_name)[:20].ljust(20),
          "Concepto": re.sub('[\W_]+', '', self.invoice_ids[0].invoice_line_ids[0].display_name)[:40].ljust(40),
          "Importe": self.amount,
          "URL_OK": baseurl + "/payment_siro/ok/",
          "URL_ERROR": baseurl + "/payment_siro/error/",
          "IdReferenciaOperacion": self.reference,
          "Detalle": []
        }
        return rqst

    def create_siro_btn(self): 
        access_token = self.acquirer_id.siro_btn_get_token()
        api_url = self.acquirer_id.get_btn_url() + "/api/Pago"
        headers = {"Authorization": "Bearer %s" % access_token}
        for res in self:
            request_data = res.siro_btn_prepare_request()
            res.siro_btn_reference = request_data['IdReferenciaOperacion']
            response = requests.post(api_url, headers=headers, json=request_data)

            if response.status_code == 200:
                _logger.info(response.json())
                req = response.json()
                res.siro_btn_reference = req['Hash']
                res.siro_btn_url = req['Url']
                res.state = 'authorized'
            else: 
                _logger.error(response.text)
                raise UserError(
                        _('Error %s ' % response.text))

    def siro_s2s_do_transaction(self, **kwargs):
        self._set_transaction_authorized()

    def siro_btn_s2s_do_transaction(self, **kwargs):
        self._set_transaction_authorized()

    @api.multi
    def _prepare_account_payment_vals(self):
        self.ensure_one()
        res = super()._prepare_account_payment_vals()
        res['name'] = self.reference
        return res

    def siro_btn_s2s_capture_transaction(self):
        self.ensure_one()
        pass
        # access_token = self.acquirer_id.siro_btn_get_token()

    def btn_process_payment_info(self,  result):
        access_token = self.acquirer_id.siro_btn_get_token()
   
        api_url = self.acquirer_id.get_btn_url() + "/api/Pago/%s/%s" % (
            self.siro_btn_reference,
            result,
        )

        headers = {"Authorization": "Bearer %s" % access_token}

        response = requests.get(api_url, headers=headers)
        _logger.info(response.content)
        if response.status_code == 200:
            req = response.json()
            if req['PagoExitoso']:
                self._set_transaction_done()
                self._reconcile_after_transaction_done()
            else:
                raise UserError(response.content)

        else:
            raise UserError(response.content)

    def siro_s2s_capture_transaction(self):
        self.acquirer_id.list_process()
        self.acquirer_id.siro_send_process()
        if self.acquirer_id.environment == 'test':
            self.acquirer_id.test_process('test')

    def siro_s2s_void_transaction(self):
        raise UserError(
            _('Las transacione de siro no puede ser canceladas una vez enviadas '))

    def siro_btn_s2s_void_transaction(self):
        self._set_transaction_cancel()


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
