
from odoo import fields, models, _
from odoo.exceptions import UserError
from datetime import timedelta
import requests
import re

import logging
_logger = logging.getLogger(__name__)


class SiroPaymentRequest(models.Model):
    _name = 'siro.payment.requests'
    _description = 'SIRO API de pago requests'

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
         ('error', 'error'),
         ('send', 'send'),
         ('pending', 'pending'),
         ('process', 'process'),
         ('authorized', ' Authorized'),
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
    default_concept = fields.Char(
        string='Concept por Defecto',
        default='0'
    )

    def action_draft(self):
        self.write({'state': 'draft', 'name': '/', 'data': ''})

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
                elif res['estado'] == 'PROCESADO':
                    data['state'] = 'authorized'
                elif res['estado'] == 'ERROR':
                    data['state'] = 'error'
                    # req.transaction_ids._set_transaction_authorized()

                req.write(data)
                ret_text = ''
                for t in res.keys():
                    ret_text += "%s: %s <br/>\n" % (t, res[t])
                self.message_post(body=_(
                    'requests check. Transaction number %s <br/>\n %s' % (req.name, ret_text)))

            else:
                req.state = 'error'
                self.message_post(
                    body=_('Requests Error. %s  %r ' % (response.status_code, response.content)))
                _logger.info(response.content)

    def prepare_line_dict(self, transaction):

        # La Factura es obligatoria como id
        # la primer factura es que vale
        if not len(transaction.invoice_ids):
            raise UserError(_('No hat factura en la transaccion %s' % transaction.name ))
        invoice_id = transaction.invoice_ids[0]
        expiration_days = 20
        date_expiration = fields.Date.from_string(invoice_id.date_due)
        second_expiration = int(invoice_id.amount_total_with_penalty * 100)

        third_expiration = second_expiration
        date_second_expiration = date_expiration + timedelta(invoice_id.company_id.days_2_expiration)
        date_third_expiration = date_expiration + timedelta(invoice_id.company_id.days_3_expiration)

        company_id = self.env.user.company_id
        #nro_comprobante = re.sub(r'[^a-zA-Z0-9]+', '', invoice_id.display_name)
        nro_comprobante = re.sub(r'[^0-9]+', '', invoice_id.display_name)

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
                ('Invoice', '{:0>15d}', int(nro_comprobante)),
                ('Concept', 'fix', self.default_concept),
                ('mes Factura', 'MMAA', invoice_id.date_invoice),
            ]
            ),
            ('cod moneda', 'fix', '0'),
            ('vencimiento', 'AAAAMMDD', date_expiration),
            ('monto', '{:0>11d}', int(transaction.amount * 100)),
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
                ('ente', '{: <15}', re.sub(
                    r'[^a-zA-Z0-9 ]+', '', company_id.name.upper())[:15]),
                ('concepto', '{: <25}',  re.sub(
                    r'[^a-zA-Z0-9 ]+', '', invoice_id.display_name.upper())[:25])
            ]),
            ('pantalla', '{: <15}', re.sub(
                r'[^a-zA-Z0-9 ]+', '', company_id.name.upper())[:15]),
            ('filler', 'fix', ' '),

            ('codigo barra', 'get_vd', [
                ('primer dv', 'get_vd',
                    [
                        ('emp', 'fix', '0447'),
                        ('concepto', 'fix', '3'),
                        ('partner id', '{:0>9d}', int(
                            transaction.partner_id.roela_ident)),
                        ('vencimiento', 'AAAAMMDD', date_expiration),
                        ('monto', '{:0>7d}', int(transaction.amount * 100)),
                        ('dias 2', '{:0>2d}', invoice_id.company_id.days_2_expiration),
                        ('monto 2', '{:0>7d}', second_expiration),
                        ('dias 3', '{:0>2d}', invoice_id.company_id.days_3_expiration),
                        ('monto 3', '{:0>7d}', third_expiration),
                        ('roela_code', '{:0>10d}', int(
                            transaction.acquirer_id.roela_code)),
                    ]
                 )
            ]),
            ('filler', '{:0>29d}', 0),
        ]

    def describre_json(self):
        self.create_register()
        res = 'ENCABEZADO<br>'

        res += self.parce_text_line([
            ('Reg code', 'fix', '0'),
            ('banelco code', 'fix', '400'),
            ('company code', 'fix', '0000'),
            ('date', 'AAAAMMDD', fields.Date.today()),
            ('filler', '{:0>264d}', 0),
        ])
        res += '<br/>---------<br/>'
        total = 0
        count_items = 0
        for transaction in self.transaction_ids:
            total += int(transaction.amount * 100)
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
            ('total', '{:0>11d}', total),
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
            ('filler', '{:0>264d}', 0),
        ])
        res += '\n'
        total = 0
        count_items = 0
        for transaction in self.transaction_ids:
            _logger.info(transaction.amount)
            total += int(transaction.amount * 100)
            count_items += 1

            # La Factura es obligatoria como id
            # la primer factura es que vale
            invoice_id = transaction.invoice_ids[0]
            expiration_days = 20
            date_expiration = fields.Date.from_string(invoice_id.date_due)
            second_expiration = int(invoice_id.amount_total_with_penalty * 100)

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
                            ('monto', '{:0>7d}', int(transaction.amount * 100)),
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
            ('total', '{:0>11d}', total),
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
