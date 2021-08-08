
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

    provider = fields.Selection(
        selection_add=[('siro', 'SIRO API'), ('siro_btn', 'SIRO botón de pagos')])
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

    @api.model
    def _cron_siro_list_process(self):
        acquirer_ids = self.search([('provider', '=', 'siro')])
        for acquirer_id in acquirer_ids:
            acquirer_id.list_process()

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
            _logger.info(response.content)
            line_def = self.get_siro_extended_format_file()
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
            ('barcode', 'char', 59),
            ('chanel', 'char', 3),
            ('void_code', 'char', 3),
            ('void_text', 'char', 20),
            ('installment', 'int', 2),
            ('card', 'char', 15),
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

    @api.model
    def _cron_siro_send_process(self):
        acquirer_ids = self.search([('provider', '=', 'siro')])
        for acquirer_id in acquirer_ids:
            acquirer_id.siro_send_process()

    def siro_send_process(self):
        self.ensure_one()
        transaction_ids = self.env['payment.transaction'].search([
            ('siro_requests_id', '=', False),
            ('acquirer_id', '=', self.id),
        ])
        _logger.info(transaction_ids);
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


class paymentTransaction(models.Model):
    _inherit = 'payment.transaction'

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

    siro_btn_timeout = fields.Datetime(
        string='Buton Timeout',
    )

    def siro_btn_prepare_request(self):
        baseurl = self.env['ir.config_parameter'].sudo(
        ).get_param('web.base.url')
        if baseurl.startswith('http://localhost'):
            baseurl = 'https://ganargan.ar'
        rqst = {
            "nro_cliente_empresa": self.acquirer_id.roela_code,
            "nro_comprobante": re.sub(r'[^a-zA-Z0-9 ]+', '', self.invoice_ids[0].display_name)[:20].rjust(20),
            "Concepto": re.sub(r'[^a-zA-Z0-9 ]+', '', self.invoice_ids[0].invoice_line_ids[0].display_name)[:40].rjust(40),
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
            response = requests.post(
                api_url, headers=headers, json=request_data)
            if response.status_code == 200:
                req = response.json()
                res.siro_btn_reference = req['Hash']
                res.siro_btn_url = req['Url']
                res.siro_btn_timeout = datetime.now() + timedelta(minutes=60)
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
        if response.status_code == 200:
            req = response.json()
            if req['PagoExitoso']:
                if self.invoice_ids[0].state == 'open':
                    self._set_transaction_done()
                    self._reconcile_after_transaction_done()
                return response.json()
            else:
                return response.json()

        else:
            raise UserError(response.content)

    def siro_s2s_capture_transaction(self):
        self.acquirer_id.list_process()
        self.acquirer_id.siro_send_process()
        if self.acquirer_id.environment == 'test':
            self.acquirer_id.test_process('test')

    def siro_s2s_void_transaction(self):
        raise UserError(
            _('Las transaciones de siro no puede ser canceladas una vez enviadas '))

    def siro_btn_s2s_void_transaction(self):
        self._set_transaction_cancel()

    def cron_siro_btn_s2s_void_transaction(self):

        transaction_ids = self.search([
            ('acquirer_id.provider', '=', 'siro_btn'),
            ('siro_btn_timeout', '<', fields.Datetime.now())
        ])
        if len(transaction_ids):
            # to do chequear la transiaccio y cancelarla
            transaction_ids.s2s_void_transaction()


class paymentToken(models.Model):

    _inherit = 'payment.token'

    provider = fields.Char(
        string='provider',
        realted='acquirer_id.provider',
    )
