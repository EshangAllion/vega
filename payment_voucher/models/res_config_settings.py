from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    payment_voucher_approval = fields.Boolean('Payment Voucher Approval',
                                              config_parameter='payment_voucher.payment_voucher_approval')
