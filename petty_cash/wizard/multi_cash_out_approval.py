from datetime import datetime
from datetime import timedelta
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class MultiCashOutApprovalWizard(models.TransientModel):
    """Multiple cash out approval wizard"""
    _name = 'multi.cash.out.approve.wizard'
    _description = 'Multiple Approval'

    def _default_cash_out_ids(self):
        """get cash out ids from active ids only in confirm state"""
        cash_outs = self.env['petty.cash.out'].browse(self._context.get('active_ids', []))
        out_ids = []
        for rec in cash_outs:
            if rec.state == 'awaiting_approval':
                out_ids.append(rec.id)
        return [(6, 0, out_ids)]

    user_id = fields.Many2one('res.users', string="Approver", required=1, default=lambda self: self.env.user)
    cash_out_ids = fields.Many2many('petty.cash.out', 'multi_cash_out_rel', 'multi_approve_id', 'state_id',
                                    string='Statements', default=_default_cash_out_ids,)
    approver_comment = fields.Char('Approver Comment')

    def approval_submission(self):
        """approve all petty cash out"""

        cash_out = []
        mail_to = False
        if not self.cash_out_ids:
            raise ValueError(_("No Cash Outs"))
        for lines in self.cash_out_ids:
            cash_out.append(str(lines.name))
            lines.write({
                'approved_by': self.user_id.id,
                'approver_comment': self.approver_comment,
            })
            # if pay by employee check the expensed amount
            if lines.petty_cash_id and lines.petty_cash_id.cash_flow < lines.expensed_amount:
                raise ValidationError(_("No cash in the petty cash Drawer. Please topup the petty cash"))
            mail_to = lines.user_id.email
            lines.change_state_to_approve()
        template_id = self.env.ref('petty_cash.mail_template_for_multi_petty_cash_out_approval')  # email template
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')  # base URL
        action = self.env.ref('petty_cash.action_petty_cash_out')  # cash out action
        url = base_url + '/web?login/#action=' + str(
            action.id) + '&view_type=tree&model=petty.cash.out'  # generate a url for user click
        context = dict(self.env.context)  # values to mail body from context
        context['mail_subject'] = "Multiple reimbursements have been approved "  # Message for mail body
        context['msg_title'] = "These reimbursements have been approved "  # Message for mail body
        context['msg_type'] = cash_out  # Message for mail body
        context['custom_url'] = url  # add url for mail body
        context['mail_to'] = mail_to if mail_to else self.user_id.email # to email
        context['approver'] = self.user_id.name  # Approver

        self.env['mail.template'].browse(template_id.id).with_context(context).send_mail(self.cash_out_ids[0].id, True)  # Send Email
