import calendar
from datetime import datetime, timedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.http import request

class PettyCashOut(models.Model):
    """
    Petty cash Handling class
    """
    _name = "petty.cash.out"
    _description = "Petty Cash Out"
    _order = "create_date desc"
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin', 'utm.mixin']


    name = fields.Char("Number", copy=False, default=lambda self: _('New'))
    cash_date = fields.Datetime(string="Requested Date", default=fields.Datetime.now)
    petty_cash_id = fields.Many2one("petty.cash", string="Petty cash Drawer", required=True)
    petty_cash_line_id = fields.Many2one('petty.cash.line', copy=False)
    employee_id = fields.Many2one('hr.employee', string="Requested Employee", required=True)
    user_id = fields.Many2one("res.users", string="User", default=lambda self: self.env.user, copy=False)
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related="company_id.currency_id", required=True, readonly=False,
                                  string='Currency')
    expensed_amount = fields.Float(string="Total Amount", copy=False, default=0.00, compute="compute_expensed_amount", tracking=True, store=True)

    expenses_line = fields.One2many('petty.cash.out.line', 'cash_out_id', copy=False, string="Cash Lines")
    reason = fields.Many2one('petty.cash.reason')
    reject_reason = fields.Char('Reject Reason')
    approved_by = fields.Many2one("res.users", string="Approved/rejected User", copy=False)
    approver_comment = fields.Char('Approve/reject Comment', copy=False)
    approved_date = fields.Datetime(string="Approved/Rejected Date", copy=False, tracking=True)
    move_id = fields.Many2many('account.move', 'cash_out_move_rel', 'cash_out_id', 'move_id', string="Journal Entries", copy=False)
    is_approve = fields.Boolean(default=False)
    is_exceed_the_minimum = fields.Boolean("Exceed the minimum amount", copy=False, store=True, compute="compute_is_exceed_the_minimum")

    state = fields.Selection([
        ('draft', 'Draft'),
        ('awaiting_approval', 'Awaiting Approval'),
        ('approved', 'Approved'),
        ('reject', 'Rejected'),
        ('complete', 'Completed')], string="Status", default="draft", tracking=True)
    is_wizard = fields.Boolean(default=False)
    remarks = fields.Text()

    @api.model
    def create(self, vals):
        """Override create method and add a sequence"""
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('petty.cash.rem') or _('New')

        result = super(PettyCashOut, self).create(vals)
        return result



    @api.depends('expenses_line')
    def compute_expensed_amount(self):
        """Calculate expensed amount"""
        for rec in self:
            expenced_amount = 0.00
            for expenced in rec.expenses_line:
                expenced_amount += expenced.amount
            rec.expensed_amount = expenced_amount

    @api.depends('expenses_line')
    def compute_is_exceed_the_minimum(self):
        """Check minimum amount in configurations and check current amount exceed the limit"""
        for rec in self:
            minimum_amount = self.env['ir.config_parameter'].sudo().get_param(
                'petty_cash.minimum_amount_for_petty_cash') or False
            if not minimum_amount or float(minimum_amount) <= 0.00 or float(minimum_amount) > rec.expensed_amount:
                rec.is_exceed_the_minimum = False
            else:
                rec.is_exceed_the_minimum = True

    def button_awaiting_approval_petty_cash_out(self):
        """functions for awaiting_approval petty cash Out"""
        self.ensure_one()
        if not self.expenses_line:
            # after pay and request reimbursements
            raise ValidationError("Please add Expenses and amounts.")

        model = self.env['ir.model'].sudo().search([('model', '=', request.params.get('model'))])
        mail_body = {
            'subject': 'Request Approval for Petty Cash Reimbursement',
            'msg_type': 'There is a reimbursement request for  your approval.',
            'msg_type2': " %(user_name)s is \
                      requesting an amount of %(amount)s. Please do the needful.""" % {
                'user_name': self.employee_id.name,
                'amount': self.currency_id.name + " " + "{:.2f}".format(self.expensed_amount)},

        }
        return {
            'name': _('Request Approval'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'petty.cash.approver.user.wizard',
            'target': 'new',
            'context': {'default_petty_cash_out_id': self.id,
                        'default_model_id': model.id,
                        'mail_body': mail_body,
                        }
        }

    def petty_cash_out_email_approved(self):
        """Send email after approve the IOU requests"""
        model = self.env['ir.model'].sudo().search([('model', '=', request.params.get('model'))])
        mail_body = {
            'subject': '%s Reimbursement has been Approved' % self.name,
            'msg_type': 'The reimbursement has been  approved.You can proceed. ',
            'status': 'approved',
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
    def button_reject_petty_cash_out(self):
        """functions for Reject petty cash Out"""
        self.ensure_one()
        model = self.env['ir.model'].sudo().search([('model', '=', request.params.get('model'))])
        mail_body = {
            'subject': '%s - Reimbursement has been Rejected' % self.name,
            'msg_type': 'The Reimbursement request has been Rejected.',
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

    def button_approve_petty_cash_out(self):
        """functions for Approve petty cash Out"""
        self.ensure_one()

        if self.petty_cash_id and self.petty_cash_id.cash_flow < self.expensed_amount:
            raise ValidationError(_("No cash in the petty cash Drawer. Please topup the petty cash "))
        return self.petty_cash_out_email_approved()


    def button_reimbursement_petty_cash_out(self):
        """Change state to a complete with transactions"""
        self.ensure_one()

        if not self.expenses_line:
            raise ValidationError("Please add Expenses lines and amounts.")

        if self.petty_cash_id.cash_balance < self.expensed_amount:
            raise ValidationError("Exceed the petty cash drawer Balance")

        for line in self.expenses_line:
            #   register expenses
            expense = self.cash_out_register_expense(line)
            if expense:
                self.move_id = [(4, expense.id)]

        #   transfer to the employee
        move = self.cash_out_cash_transfer_to_employee()
        if move:
            self.move_id = [(4, move.id)]

        #   reconcile transactions
        self.bank_reconcile()
        self.create_transactions_in_petty_cash()
        self.petty_cash_id.cash_out += self.expensed_amount
        self.state = "complete"


    def bank_reconcile(self):
        """Reconcile accounts transactions"""
        account_move_ids = []
        for rec in self.move_id:
            account_move_ids += rec.line_ids
        account_move_lines_to_reconcile = self.env['account.move.line']

        for line in account_move_ids:
            if line.account_id.internal_type == 'payable' and not line.reconciled:
                account_move_lines_to_reconcile |= line
        account_move_lines_to_reconcile.sudo().reconcile()

    def create_transactions_in_petty_cash(self):
        #   Create a log un relevant petty cash logins after finished
        cash_line_id = self.env['petty.cash.line'].create({
                'name': self.name,
                'petty_cash_id': self.petty_cash_id.id,
                'from_acc': self.petty_cash_id.journal_id.default_account_id.id,
                'to_acc': self.employee_id.address_home_id.property_account_payable_id.id,
                'reason': self.reason.name,
                'amount': self.expensed_amount,
                'type': 'reimbursement',
                'user_id': self.user_id.id,
                'employee_id': self.employee_id.id,
                'approved_by': self.approved_by.id,
                'cash_reimbursement_id': self.id,
            })
        self.petty_cash_line_id = cash_line_id.id

    def button_petty_cash_request_reject(self, reason):
        """functions for Reject Reimbursement"""
        self.ensure_one()
        self.state = "reject"
        self.approver_comment = reason
        self.approved_date = datetime.now()
        self.approved_by = self.env.user

    def button_function_set_to_draft(self,):
        """functions for Set to draft petty cash """
        self.ensure_one()
        self.state = "draft"

    def button_view_journal_entries(self):
        """view journal entries related to this"""
        self.ensure_one()
        context = self.env.context.copy()
        action = self.env.ref('account.action_move_journal_line').read()[0]
        action['domain'] = [('id', 'in', self.move_id.ids)]
        action['view_mode'] = 'form'
        action['context'] = context
        return action

    def cash_out_register_expense(self, line):
        """Create journal entries for employee_expenses"""
        if not self.employee_id.address_home_id:
            raise ValidationError("Please add a employee private address ")
        entry_vals = {
            'date': datetime.now().date(),
            'journal_id': self.petty_cash_id.journal_id.id,
            'ref': "Petty Cash Expense - " + str(self.name),
            'company_id': int(self.company_id.id),
            'currency_id': int(self.currency_id.id),
            'line_ids': [
                (0, 0, {
                    'account_id': self.employee_id.address_home_id.property_account_payable_id.id,
                    'name': "Petty Cash Expense - " + str(self.name),
                    'partner_id': self.employee_id.address_home_id.id,
                    'credit': line.amount,
                    'debit': 0.00,
                }),
                (0, 0, {
                    'account_id': line.expense_account_id.id,
                    'name': "Petty Cash Expense - " + str(self.name),
                    'partner_id': self.employee_id.address_home_id.id,
                    'credit': 0.00,
                    'debit': line.amount,
                })
            ]
        }
        journal_entry = self.env['account.move'].sudo().create(entry_vals)
        journal_entry.sudo().action_post()
        return journal_entry

    def change_state_to_approve(self):
        """Change state to awaiting_approval"""
        self.state = "approved"
        self.approved_date = datetime.now()
        self.is_approve = False

    def cash_out_cash_transfer_to_employee(self):
        """Create journal entries for payment of employee"""
        if not self.employee_id.address_home_id:
            raise ValidationError("Please add a employee private address ")
        entry_vals = {
            'date': datetime.now().date(),
            'journal_id': self.petty_cash_id.journal_id.id,
            'ref': "Petty Cash Reimbursement Payment- " + str(self.name),
            'company_id': int(self.company_id.id),
            'currency_id': int(self.currency_id.id),
            'line_ids': [
                (0, 0, {
                    'account_id': self.petty_cash_id.journal_id.default_account_id.id,
                    'name': "Petty Cash Reimbursement payment - " + str(self.name),
                    'partner_id': self.employee_id.address_home_id.id,
                    'credit':  self.expensed_amount,
                    'debit': 0.00
                }),
                (0, 0, {
                    'account_id': self.employee_id.address_home_id.property_account_payable_id.id,
                    'name': "Petty Cash Out Payment - " + str(self.name),
                    'partner_id': self.employee_id.address_home_id.id,
                    'credit': 0.00,
                    'debit': self.expensed_amount,
                })
            ]
        }
        journal_entry = self.env['account.move'].sudo().create(entry_vals)
        journal_entry.sudo().action_post()
        return journal_entry

    def change_state_to_awaiting_approval(self):
        """Change state to awaiting_approvals"""
        self.state = "awaiting_approval"


class PettyCashOutLine(models.Model):
    """Petty cash out lines class"""
    _name = "petty.cash.out.line"
    _description = "Petty Cash Out Line"

    def _domain_expense_account_id(self):
        """display only expenses accounts"""
        expenses = self.env.ref('account.data_account_type_expenses').id
        domain = [('user_type_id', '=', expenses)]
        return domain

    name = fields.Char("Description", required=True)
    cash_out_id = fields.Many2one('petty.cash.out', string="Petty Cash")
    expense_account_id = fields.Many2one('account.account', string="Expense Account", required=True,
                                         domain=_domain_expense_account_id)
    account_analytic_id = fields.Many2one('account.analytic.account', store=True, string='Analytic Account', readonly = False)
    attachment_id = fields.Many2many('ir.attachment', 'petty_attach_id', 'attach_id', 'petty_id', string="Attachment")
    amount = fields.Float("Amount", required=True, default=0.00)


class IrAttachment(models.Model):
    """Inherit Attachments class  """
    _inherit = 'ir.attachment'

    petty_attach_id = fields.Many2many('petty.cash.out.line', 'petty_attach_id', 'petty_id', 'attach_id', string="Petty cash")
    petty_release_id = fields.Many2many('petty.cash.release.line', 'petty_release_attach_id', 'release_id', 'attach_id',
                                        string="IOU Requests")