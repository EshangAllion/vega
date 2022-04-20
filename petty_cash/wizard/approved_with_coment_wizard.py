from odoo import fields, models, api
from datetime import datetime
from datetime import timedelta


class PettyCashApprovedCommentWizard(models.TransientModel):
    """
    user select wizard for select the approver
    """
    _name = 'petty.cash.approved.comment.wizard'
    _description = 'Comments'

    user_id = fields.Many2one('res.users', string="Approver",  required=1, default=lambda self: self.env.user)
    model_id = fields.Many2one('ir.model')
    approver_comment = fields.Char('Approver Comment')

    def approval_submission(self):
        """Send the notifications email and update the linked data records"""
        template_id = self.env.ref('petty_cash.mail_template_after_approved_petty_cash_in')  #  email template
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        url = base_url + '/web?login/#id=' + str(self._context.get('active_id')) + '&view_type=form&model='\
              + str(self._context.get('active_model'))  # generate a url for user click
        context = self.env.context.get('mail_body')     # values to mail body from context
        context['custom_url'] = url    # add url for mail body

        linked_data = self.env[self._context.get('active_model')].sudo().search([('id', '=', self._context.get('active_id'))], limit=1)
        context['mail_to_name'] = linked_data.user_id.name
        context['mail_to'] = linked_data.user_id.partner_id.email
        # change status of linked data
        linked_data.write({
            'approved_by': self.user_id.id,
            'approver_comment': self.approver_comment,
        })
        linked_data.change_state_to_approve()
        self.env['mail.template'].browse(template_id.id).with_context(context).send_mail(self.id, True)
