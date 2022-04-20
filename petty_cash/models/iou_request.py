import calendar
from datetime import datetime, timedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.http import request

class PettyCashRelease(models.Model):
    """
    Petty cash Release Handling class
    """
    _name = "petty.cash.release"
    _description = "IOU Request"
    _order = "create_date desc"
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin', 'utm.mixin']


    name = fields.Char("Number", copy=False, default=lambda self: _('New'))
    release_date = fields.Datetime(string="Requested Date",copy=False, default=fields.Datetime.now)
    petty_cash_id = fields.Many2one("petty.cash", string="Petty Cash Drawer", required=True)
    employee_id = fields.Many2one('hr.employee', string="Requested Employee", required=True)
    user_id = fields.Many2one("res.users", string="Responsible Person", copy=False, default=lambda self: self.env.user, required=True)
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one('res.currency', related="company_id.currency_id", required=True, readonly=False,
                                  string='Currency')
    released_amount = fields.Float(string="Amount", copy=False, default=0.00,  tracking=True, store=True, required=True)
    expensed_amount = fields.Float(string="Expensed Amount", compute="_compute_balanced_amount", copy=False, default=0.00, tracking=True, store=True)
    balanced_amount = fields.Float(string="Balanced Amount", compute="_compute_balanced_amount", store=True)
    reason = fields.Many2one('petty.cash.reason',)
    approved_by = fields.Many2one("res.users", string="Approved/Rejected User", copy=False, readonly=True)
    approver_comment = fields.Char('Approved/Rejected Reason', copy=False, tracking=True)
    approved_date = fields.Datetime(string="Approved/Rejected Date", copy=False, tracking=True)
    move_id = fields.Many2many('account.move', 'cash_release_move_rel', 'cash_out_id', 'move_id', string="Journal Entries",
                               copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('awaiting_approval', 'Awaiting Approval'),
        ('approved', 'Approved'),
        ('reject', 'Rejected'),
        ('released', 'Cash Issued'),
        ('complete', 'Completed')], string="Status", default="draft", copy=False, tracking=True)

    remarks = fields.Text()
    comment = fields.Text()
    petty_cash_line_id = fields.Many2one('petty.cash.line')
    expenses_line = fields.One2many('petty.cash.release.line', 'cash_release_id', string='Expenses line')

    is_wizard = fields.Boolean(default=False)

    @api.model
    def create(self, vals):
        """Override create method and add a sequence"""
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('petty.cash.iou') or _('New')

        result = super(PettyCashRelease, self).create(vals)
        return result

    @api.depends('released_amount', 'expensed_amount', 'expenses_line')
    def _compute_balanced_amount(self):
        """Compute balanced amount and expensed amount """
        for rec in self:
            expensed_amount = 0.00
            for lines in self.expenses_line:
                expensed_amount += lines.amount
            rec.expensed_amount = expensed_amount
            rec.balanced_amount = rec.released_amount - expensed_amount

    def button_request_approval_petty_cash_release(self):
        """functions for awaiting_approval petty cash Issued"""
        if self.released_amount == 0.00:
            raise ValidationError("Released Amount is Zero")
        if self.petty_cash_id.cash_balance < self.released_amount:
            raise ValidationError("Exceed the petty cash balance ")
        model = self.env['ir.model'].search([('model', '=', request.params.get('model'))])
        mail_body = {
            'subject': 'Approval for Petty Cash IOU-Request',
            'msg_type': 'There is a pending IOU request for  your approval.',
            'msg_type2': "%(user_name)s is requesting amount of %(amount)s. Please do the needful." % {'user_name': self.employee_id.name, 'amount': self.currency_id.name + " " + "{:.2f}".format(self.released_amount)},
        }
        return {
            'name': _('Request approval'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'petty.cash.approver.user.wizard',
            'target': 'new',
            'context': {
                        'default_model_id': model.id,
                        'mail_body': mail_body,
                        }
        }

    def button_approve_petty_cash_release(self):
        """functions for Approve petty cash Issue"""
        self.ensure_one()

        if self.petty_cash_id.cash_balance < self.released_amount:
            raise ValidationError("Exceed the petty cash balance ")
        model = self.env['ir.model'].sudo().search([('model', '=', request.params.get('model'))])
        mail_body = {
            'subject': '%s IOU Request has been Approved' % self.name,
            'msg_type': 'The IOU  Request has been  approved.You can proceed. ',
            'status': 'approved',
        }

        return {
            'name': _('Approve'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'petty.cash.approved.comment.wizard',
            'target': 'new',
            'context': {
                        'default_model_id': model.id,
                        'mail_body': mail_body,
                        }
        }

    def button_reject_petty_cash_release(self):
        """functions for Reject petty cash Release"""
        self.ensure_one()
        model = self.env['ir.model'].sudo().search([('model', '=', request.params.get('model'))])
        mail_body = {
            'subject': '%s - IOU Request has been Rejected' % self.name,
            'msg_type': 'The IOU request has been Rejected. ',
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

    def create_transactions_in_petty_cash(self):
        #   Create a log un relevant petty cash logins after finished
        cash_line_id = self.env['petty.cash.line'].create({
                'name': self.name,
                'petty_cash_id': self.petty_cash_id.id,
                'from_acc': self.petty_cash_id.journal_id.default_account_id.id,
                'to_acc': self.employee_id.address_home_id.property_account_payable_id.id,
                'reason': self.reason.name,
                'amount': self.released_amount,
                'type': 'iou_request',
                'user_id': self.user_id.id,
                'employee_id': self.employee_id.id,
                'approved_by': self.approved_by.id,
                'cash_release_id': self.id,
            })
        self.petty_cash_line_id = cash_line_id.id

    def button_petty_cash_released(self):
        """functions for released petty cash to employee"""
        self.ensure_one()
        if self.petty_cash_id and self.petty_cash_id.cash_flow < self.released_amount:
            raise ValidationError(_("No cash in the petty cash. Request a petty cash first"))

        move_id = self.create_journal_entries()
        self.move_id = [(4, move_id.id)]
        self.calculate_petty_cash_transactions()
        self.create_transactions_in_petty_cash()
        self.state = "released"

    def button_petty_cash_complete(self):
        """functions for Done petty cash and create journal entries """
        self.ensure_one()
        if not self.expensed_amount or self.expensed_amount == 0.00:
            raise ValidationError(_("Please add expenses lines"))

        if self.expensed_amount > self.released_amount:
            over_balance = self.expensed_amount - self.released_amount
            raise ValidationError(_("Expensed amount exceeds by %(amount)s. Please create a reimbursement record to settle the extra %(amount)s." % {'amount': over_balance}))

        for line in self.expenses_line:
            #   Create journal entries for expenses ony by one
            journal_entry = self.create_journal_entries_for_expenses(line)
            self.move_id = [(4, journal_entry.id)]

        if self.balanced_amount > 0.00:
            #    create a journal entry for balance amount
            move_id = self.create_journal_entries_balance(self.balanced_amount)
            #   Update petty cash with balance
            self.petty_cash_id.cash_out -= self.balanced_amount
            self.move_id = [(4, move_id.id)]

        # entries reconcile
        account_move_ids = []
        for rec in self.move_id:
            account_move_ids+= rec.line_ids
        account_move_lines_to_reconcile = self.env['account.move.line']

        for line in account_move_ids:
            if line.account_id.internal_type == 'receivable' and not line.reconciled:
                account_move_lines_to_reconcile |= line
        account_move_lines_to_reconcile.sudo().reconcile()
        self.petty_cash_line_id.amount = self.expensed_amount
        self.state = "complete"


    def calculate_petty_cash_transactions(self):
        """ functions for calculate petty cash Transactions"""
        if self.petty_cash_id.cash_balance < self.released_amount:
            raise ValidationError("Exceed the cash balance")
        self.petty_cash_id.cash_out += self.released_amount

    def button_view_journal_entries(self):
        """view journal entries related to this"""
        self.ensure_one()
        context = self.env.context.copy()
        action = self.env.ref('account.action_move_journal_line').read()[0]
        action['domain'] = [('id', 'in', self.move_id.ids)]
        action['view_mode'] = 'form'
        action['context'] = context
        return action

    def create_journal_entries(self):
        """Create journal entries for cash Issue"""
        if not self.employee_id.address_home_id:
            raise ValidationError("Please add a employee private address ")

        entry_vals = {
            'date': self.release_date,
            'journal_id': self.petty_cash_id.journal_id.id,
            'ref': "Petty Cash Issue - " + str(self.name),
            'company_id': int(self.company_id.id),
            'currency_id': int(self.currency_id.id),
            'line_ids': [

                (0, 0, {
                    'account_id': self.petty_cash_id.journal_id.default_account_id.id,
                    'name': "Petty Cash Issue - " + str(self.name),
                    'partner_id': self.employee_id.address_home_id.id,
                    'credit': self.released_amount,
                    'debit': 0.00,
                }),
                (0, 0, {
                    'account_id': self.employee_id.address_home_id.property_account_receivable_id.id,
                    'name': "Petty Cash Issue - " + str(self.name),
                    'partner_id': self.employee_id.address_home_id.id,
                    'credit': 0.00,
                    'debit': self.released_amount,
                })
            ]
        }
        journal_entry = self.env['account.move'].sudo().create(entry_vals)
        journal_entry.sudo().action_post()
        return journal_entry

    def create_journal_entries_for_expenses(self, line):
        """Create journal entries for register expenses of employee"""
        entry_vals = {
            'date': datetime.now().date(),
            'journal_id': self.petty_cash_id.journal_id.id,
            'ref': "Petty Cash reimbursement - " + str(self.name),
            'company_id': int(self.company_id.id),
            'currency_id': int(self.currency_id.id),
            'line_ids': [
                (0, 0, {
                    'account_id': self.employee_id.address_home_id.property_account_receivable_id.id,
                    'name': "Petty Cash reimbursement - " + str(self.name) + ' - '+ str(line.name),
                    'partner_id': self.employee_id.address_home_id.id,
                    'credit': line.amount,
                    'debit': 0.00,
                }),
                (0, 0, {
                    'account_id': line.expense_account_id.id,
                    'name': "Petty Cash reimbursement - " + str(self.name) + ' - '+ str(line.name),
                    'analytic_account_id': line.account_analytic_id.id,
                    'partner_id': self.employee_id.address_home_id.id,
                    'credit': 0.00,
                    'debit': line.amount,
                })
            ]
        }
        journal_entry = self.env['account.move'].sudo().create(entry_vals)
        journal_entry.sudo().action_post()
        return journal_entry

    def create_journal_entries_balance(self, amount):
        """Create journal entries for cash Update Balance"""
        if not self.employee_id.address_home_id:
            raise ValidationError("Please add a employee private address ")

        entry_vals = {
            'date': datetime.now().date(),
            'journal_id': self.petty_cash_id.journal_id.id,
            'ref': "Petty Cash Balance - " + str(self.name),
            'company_id': int(self.company_id.id),
            'currency_id': int(self.currency_id.id),
            'line_ids': [
                (0, 0, {
                    'account_id': self.employee_id.address_home_id.property_account_receivable_id.id,
                    'name': "Petty Cash Balance - " + str(self.name),
                    'partner_id': self.employee_id.address_home_id.id,
                    'credit': amount,
                    'debit': 0.00,
                }),

                (0, 0, {
                    'account_id': self.petty_cash_id.journal_id.default_account_id.id,
                    'name': "Petty Cash Balance - " + str(self.name),
                    'partner_id': self.employee_id.address_home_id.id,
                    'credit': 0.00,
                    'debit': amount,
                })
            ]
        }
        journal_entry = self.env['account.move'].sudo().create(entry_vals)
        journal_entry.sudo().action_post()
        return journal_entry

    def change_state_to_awaiting_approval(self):
        """Change state to awaiting_approvals"""
        self.state = "awaiting_approval"

    def change_state_to_approve(self):
        """Change state to Approve"""
        self.state = "approved"
        self.approved_date = datetime.now()

    def set_to_draft(self, reason=False):
        """functions for Set to draft petty cash """
        self.ensure_one()
        self.state = "draft"

    def button_petty_cash_request_reject(self, reason):
        """functions for Cancel petty cash """
        self.ensure_one()
        self.state = "reject"
        self.approver_comment = reason
        self.approved_date = datetime.now()
        self.approved_by = self.env.user


class PettyCashReleaseLine(models.Model):
    """Petty cash out lines class"""
    _name = "petty.cash.release.line"
    _description = " IOU requests Line"

    def _domain_expense_account_id(self):
        """display only expenses accounts"""
        expenses = self.env.ref('account.data_account_type_expenses').id
        domain = [('user_type_id', '=', expenses)]
        return domain

    name = fields.Char("Description", required=True)
    cash_release_id = fields.Many2one('petty.cash.release', string="IOU Requests")
    expense_account_id = fields.Many2one('account.account', string="Expense Account",
                                         domain=_domain_expense_account_id)
    account_analytic_id = fields.Many2one('account.analytic.account', store=True, string='Analytic Account', readonly = False)
    attachment_id = fields.Many2many('ir.attachment', 'petty_release_attach_id', 'attach_id', 'release_id', string="Attachment")
    amount = fields.Float("Amount", required=True, default=0.00)






