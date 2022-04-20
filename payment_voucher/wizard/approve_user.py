from odoo import fields, models, api
from datetime import datetime
from datetime import timedelta


class PaymentVoucherApproverUserWizard(models.TransientModel):
    _name = 'payment.voucher.approver.user.wizard'
    _description = 'Approval'

    user_id = fields.Many2one('res.users', string="Approver", required=1, domain=lambda self: [('groups_id', 'in', self.env.ref('payment_voucher.group_account_payment_voucher_approval_security').id)])
    voucher_id = fields.Many2one('payment.voucher')
    model_id = fields.Many2one('ir.model')

    def approval_submission(self):
        if self.voucher_id:
            template_id = self.env.ref('payment_voucher.mail_template_for_payment_voucher_approval')
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            url = base_url + '/web?login/#id=' + str(self._context.get('active_id')) + '&view_type=form&model=payment.voucher'
            self.voucher_id.write({
                'custom_url': url,
                'state': 'waiting_approval',
                'triggered_approval': True,
            })
            self.env['mail.template'].browse(template_id.id).send_mail(self.id, True)
            return True
