from odoo import fields, models, api
from datetime import datetime
from datetime import timedelta


class PettyCashApproverUserWizard(models.TransientModel):
    """
    user select wizard for select the approver
    """
    _name = 'petty.cash.approver.user.wizard'
    _description = 'Approval'

    user_id = fields.Many2one('res.users', string="Approver",  required=1, domain=lambda self: [('groups_id', 'in', self.env.ref('petty_cash.petty_cash_group_manager').id)])
    model_id = fields.Many2one('ir.model')

    def approval_submission(self):
        """Send the notifications email and update the linked data records"""
        template_id = self.env.ref('petty_cash.mail_template_for_petty_cash_out_approval')  #  email template
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        url = base_url + '/web?login/#id=' + str(self._context.get('active_id')) + '&view_type=form&model='\
              + str(self._context.get('active_model'))  # generate a url for user click
        context = self.env.context.get('mail_body')     # values to mail body from context
        context['custom_url'] = url    # add url for mail body

        if context.get('actions') == "confirm":
            context['mail_to'] = self.user_id.email
        else:
            context['mail_to'] = self.env.user.email
        linked_data = self.env[self._context.get('active_model')].sudo().search([('id', '=', self._context.get('active_id'))], limit=1)
        # change status of linked data to confirm
        linked_data.change_state_to_awaiting_approval()
        self.env['mail.template'].browse(template_id.id).with_context(context).send_mail(self.id, True)
