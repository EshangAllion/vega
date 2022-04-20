import calendar
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.http import request
from odoo.exceptions import ValidationError


class PettyCashIN(models.Model):
    """
    Petty cash Handling class for cash in
    """
    _name = "petty.cash.in"
    _description = "Petty Cash Top Up"
    _order = "create_date desc"
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin', 'utm.mixin']

    name = fields.Char("Number",copy=False, default=lambda self: _('New'))
    request_date = fields.Datetime(string="Requested Date", default=fields.Datetime.now, copy=False,)
    cash_date = fields.Datetime(string="Processed Date", tracking=True, copy=False,)
    petty_cash_id = fields.Many2one("petty.cash", string="Petty Cash Drawer", copy=False, required=True)
    user_id = fields.Many2one("res.users", string="Requested User", default=lambda self: self.env.user,copy=False, required=True)
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one('res.currency', related="company_id.currency_id", required=True, readonly=False,
                                  string='Currency')
    amount = fields.Float(string="Amount", default=0.00, copy=False,  tracking=True)
    reason = fields.Char(string="Reason")
    note = fields.Char(string="Note")
    approved_by = fields.Many2one("res.users", string="Approved/Rejected User", copy=False, tracking=True)
    approved_date = fields.Datetime(string="Approved/Rejected Date", copy=False, tracking=True)
    approver_comment = fields.Char("Approve/Reject Comment", copy=False, tracking=True)
    petty_cash_journal_id = fields.Many2one('account.journal', related="petty_cash_id.journal_id")
    journal_id = fields.Many2one('account.journal', string="Source Account", domain="[('type','in',('bank','cash')),('id','!=',petty_cash_journal_id)]" )
    move_id = fields.Many2one('account.move', string="Journal Entries", copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('awaiting_approval', 'Awaiting Approval'),
        ('approved', 'Approved'),
        ('reject', 'Rejected'),
        ('toppedup', 'Topped Up')], string="Status", default="draft", tracking=True)

    petty_cash_line_id = fields.Many2one('petty.cash.line', copy=False,)
    is_wizard = fields.Boolean(default=False)
    @api.model
    def create(self, vals):
        """Override create method and add a sequence"""
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('petty.cash.topup') or _('New')
        result = super(PettyCashIN, self).create(vals)
        return result

    def button_awaiting_approval_petty_cash_in(self):
        """functions for awaiting_approval petty cash IN"""
        self.ensure_one()
        if not self.amount or not self.amount > 0.00:
            raise ValidationError("The amount must be more than Zero")
        model = self.env['ir.model'].sudo().search([('model', '=', request.params.get('model'))])
        mail_body = {
            'subject': 'Request Approval for Petty Cash Top-Up',
            'msg_type': '%(user_name)s is requesting an amount of %(amount)s for petty cash top up' % {'user_name': self.user_id.name, 'amount': self.currency_id.name + " " + "{:.2f}".format(self.amount)},
        }
        return {
            'name': _('Request for Approval'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'petty.cash.approver.user.wizard',
            'target': 'new',
            'context': {'default_petty_cash_out_id': self.id,
                        'default_model_id': model.id,
                        'mail_body': mail_body,
                        }
        }


    def button_approve_petty_cash_in(self):
        """functions for Approve petty cash IN"""
        self.ensure_one()
        if not self.journal_id:
            raise ValidationError(_("Please add a source account to the transaction"))
        model = self.env['ir.model'].sudo().search([('model', '=', request.params.get('model'))])
        mail_body = {
            'subject': '%s - Petty Cash Top-Up has been approved' % self.name,
            'msg_type': 'The Petty Cash Top-Up request has been approved. You can proceed.',
        }

        return {
            'name': _('Approve'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'petty.cash.approved.comment.wizard',
            'target': 'new',
            'context': {'default_petty_cash_out_id': self.id,
                        'default_model_id': model.id,
                        'mail_body': mail_body,
                        }
        }

    def button_reject_petty_cash_in(self):
        """functions for Reject petty cash IN"""
        self.ensure_one()
        model = self.env['ir.model'].sudo().search([('model', '=', request.params.get('model'))])
        mail_body = {
            'subject': '%s - Petty Cash Top-Up has been Rejected' % self.name,
            'msg_type': 'The Petty Cash Top-Up request has been Rejected.',
        }

        return {
            'name': _('Rejected'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'petty.cash.draft.reason',
            'target': 'new',
            'context': {'default_petty_cash_out_id': self.id,
                        'default_model_id': model.id,
                        'mail_body': mail_body,
                        }
        }


    def button_petty_cash_toppedup(self):
        """functions for toppedup petty cash IN"""
        self.ensure_one()
        if not self.cash_date:
            self.cash_date = datetime.now()
        self.calculate_petty_cash_transactions()
        self.create_transactions_in_petty_cash()
        self.state = 'toppedup'

    def calculate_petty_cash_transactions(self):
        """ functions for calculate petty cash Transactions"""
        journal_entry_id = self.create_journal_entries()
        amount = self.petty_cash_id.cash_flow + self.amount
        self.petty_cash_id.write({
            #   update amount in petty cash drawer
            'cash_flow': amount
        })
        self.write({
            'move_id': journal_entry_id.id,
        })

    def create_journal_entries(self):
        """Create journal entries"""
        entry_vals = {
            'date': self.cash_date,
            'journal_id': self.petty_cash_id.journal_id.id,
            'ref': "Petty Cash Top Up - " + str(self.name),
            'company_id': int(self.company_id.id),
            'currency_id': int(self.currency_id.id),
            'line_ids': [
                (0, 0, {
                    'account_id': self.journal_id.default_account_id.id,
                    'name': "Petty Cash Top Up - " + str(self.name),
                    'credit': self.amount,
                    'debit': 0.00,
                }),
                (0, 0, {
                    'account_id': self.petty_cash_id.journal_id.default_account_id.id,
                    'name': "Petty Cash Top Up - " + str(self.name),
                    'credit': 0.00,
                    'debit': self.amount,
                })
            ]
        }
        journal_entry = self.env['account.move'].sudo().create(entry_vals)
        journal_entry.sudo().action_post()
        return journal_entry


    def change_state_to_awaiting_approval(self):
        """Change state to awaiting_approval"""

        self.state = "awaiting_approval"

    def change_state_to_approve(self):
        """Change state to Approve"""

        self.state = "approved"
        self.approved_date = datetime.now()

    def button_petty_cash_request_reject(self, reason):
        """functions for Cancel petty cash """
        self.ensure_one()
        self.state = "reject"
        self.approved_by = self.env.user
        self.approver_comment = reason
        self.approved_date = datetime.now()

    def set_to_draft(self, reason=False):
        """functions for Set to draft petty cash """
        self.ensure_one()
        self.is_wizard = True
        self.state = "draft"

    def create_transactions_in_petty_cash(self):
        #   Create a log un relevant petty cash logins after finished
        cash_line_id = self.env['petty.cash.line'].create({
                'name': self.name,
                'petty_cash_id': self.petty_cash_id.id,
                'from_acc': self.journal_id.default_account_id.id,
                'to_acc': self.petty_cash_id.journal_id.default_account_id.id,
                'reason': self.reason,
                'amount': self.amount,
                'type': 'topup',
                'user_id': self.user_id.id,
                'approved_by': self.approved_by.id,
                'petty_cash_in': self.id,
            })
        self.petty_cash_line_id = cash_line_id.id

    def button_view_journal_entries(self):
        """view journal entries related to this"""
        self.ensure_one()
        context = self.env.context.copy()
        action = self.env.ref('account.action_move_journal_line').read()[0]
        action['domain'] = [('id', 'in', self.move_id.ids)]
        action['view_mode'] = 'form'
        action['context'] = context
        return action
