from odoo import fields, models, api
from datetime import datetime
from datetime import timedelta


class PaymentVoucherApproveCommentWizard(models.TransientModel):
    _name = 'payment.voucher.approve.comment.wizard'
    _description = 'Approval/Reject Comment'

    comment = fields.Text(string="Approve/Reject Comment")
    voucher_id = fields.Many2one('payment.voucher')
    model_id = fields.Many2one('ir.model')
    action = fields.Char(string="Action")

    def approval_submission(self):
        if self.action == 'Approved':
            if self.voucher_id:
                template_id = self.env.ref('payment_voucher.mail_template_for_approved_payment_voucher')
                base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                url = base_url + '/web?login/#id=' + str(self.voucher_id.id) + '&view_type=form&model=payment.voucher'
                self.voucher_id.write({
                    'custom_url': url,
                    'approved_by': self._uid,
                    'state': 'approved',
                    'approve_Date': datetime.today().date(),
                    'comment': self.comment,
                })
                self.env['mail.template'].browse(template_id.id).send_mail(self.id, True)

        if self.action == 'Rejected':
            if self.voucher_id:
                template_id = self.env.ref('payment_voucher.mail_template_for_reject_payment_voucher')
                base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                url = base_url + '/web?login/#id=' + str(self.voucher_id.id) + '&view_type=form&model=payment.voucher'
                self.voucher_id.write({
                    'custom_url': url,
                    'approved_by': self._uid,
                    'state': 'cancel',
                    'approve_Date': datetime.today().date(),
                    'comment': self.comment,
                    'triggered_approval': False,
                })
                self.env['mail.template'].browse(template_id.id).send_mail(self.id, True)
