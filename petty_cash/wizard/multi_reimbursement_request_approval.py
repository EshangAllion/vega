from odoo import fields, models, api, _
from datetime import datetime
from datetime import timedelta


class MultiCashOutApprovalWizard(models.TransientModel):
    """Multiple cash out confirm wizard"""
    _name = 'multi.cash.out.confirm.wizard'
    _description = 'Multiple Confirm'

    def _default_cash_out_ids(self):
        """get cash out ids from active ids only in confirm state"""
        cash_outs = self.env['petty.cash.out'].browse(self._context.get('active_ids', []))
        out_ids = []
        for rec in cash_outs:
            if rec.state == 'draft' and rec.is_exceed_the_minimum:
                out_ids.append(rec.id)
        return [(6, 0, out_ids)]

    user_id = fields.Many2one('res.users', string="Approver", required=1, domain=lambda self: [('groups_id', 'in', self.env.ref('petty_cash.petty_cash_group_manager').id)])
    cash_out_ids = fields.Many2many('petty.cash.out', 'multi_cash_out_confirm_rel', 'multi_approve_id', 'state_id',
                                    string='Statements', default=_default_cash_out_ids,)
    custom_url = fields.Char()

    def approval_submission(self):
        """approve all petty cash out"""

        #  Send the notifications email and update the linked data records
        cash_out = []
        if not self.cash_out_ids:
            raise ValueError(_("No Cash Outs"))
        for lines in self.cash_out_ids:
            """
            create email message with requested cash out 
            """
            cash_out.append(str(lines.name))
            lines.write({
                'is_approve': True
            })
            lines.change_state_to_awaiting_approval()
        template_id = self.env.ref('petty_cash.mail_template_for_multi_petty_cash_out_approval')  # email template
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')  # base URL
        action = self.env.ref('petty_cash.action_petty_cash_out_multi_approve')  # cash out action
        url = base_url + '/web?login/#action=' + str(action.id) + '&view_type=tree&model=petty.cash.out'  # generate a url for user click
        context = dict(self.env.context)  # values to mail body from context
        context['mail_subject'] = "Request Approval for multiple reimbursement(s)"  # Message for mail body
        context['msg_title'] = "Request approve for reimbursement(s)"  # Message for mail body
        context['msg_type'] = cash_out  # Message for mail body
        context['custom_url'] = url  # add url for mail body
        context['mail_to'] = self.user_id.email  # to email
        context['approver'] = self.user_id.name  # Approver

        self.env['mail.template'].browse(template_id.id).with_context(context).send_mail(self.cash_out_ids[0].id, True)  # Send Email


