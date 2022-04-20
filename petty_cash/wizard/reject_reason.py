from odoo import fields, models, api
from datetime import datetime
from datetime import timedelta


class PettyCashDraftWizard(models.TransientModel):
    """
    wizard for Draft reason
    """
    _name = 'petty.cash.draft.reason'
    _description = 'Approval'

    user_id = fields.Many2one('res.users', string="User", invisible=True, required=1, default=lambda self: self.env.user)
    cancel_reason = fields.Char("Reject Reason")

    def approval_submission(self):
        """update the linked data records"""
        template_id = self.env.ref('petty_cash.mail_template_for_petty_cash_reject')    # email template
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        url = base_url + '/web?login/#id=' + str(self._context.get('active_id')) + '&view_type=form&model='\
              + str(self._context.get('active_model'))  # generate a url for user click
        context = self.env.context.get('mail_body')     # values to mail body from context
        context['custom_url'] = url    # add url for mail body
        context['mail_to'] = self.user_id.email
        linked_data = self.env[self._context.get('active_model')].search([('id', '=', self._context.get('active_id'))],
                                                                         limit=1)
        # reject pety cash
        linked_data.button_petty_cash_request_reject(reason=self.cancel_reason)
        self.env['mail.template'].browse(template_id.id).with_context(context).send_mail(self.id, True)