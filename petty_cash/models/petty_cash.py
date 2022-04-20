import json
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class PettyCash(models.Model):
    """
    Petty cash Handling class
    """
    _name = "petty.cash"
    _description = "Petty Cash"
    _order = "end_date desc"

    @api.model
    def default_get(self, default_fields):
        """ Compute default start date and end date
        using the default values computed for the other fields.
        """
        res = super(PettyCash, self).default_get(default_fields)

        petty_cashes = self.env['petty.cash'].search([], order="end_date desc", limit=1)
        date_range = self.env['ir.config_parameter'].sudo().get_param('petty_cash.petty_cash_date_range') or False
        if petty_cashes:
            start_date = petty_cashes.end_date + timedelta(days=1)
            res['start_date'] = start_date
            if not date_range:
                date_range = 30
            else:
                date_range = int(date_range)
            res['end_date'] = start_date + timedelta(days=date_range)
            # res['end_date'] = start_date.replace(day=calendar.monthrange(start_date.year, start_date.month)[1])
        else:
            today = fields.Date.today()
            res['start_date'] = today
            if not date_range:
                date_range = 30
            else:
                date_range = int(date_range)
            res['end_date'] = today + timedelta(days=date_range)
        return res

    name = fields.Char(readonly=True, default=lambda self: _('New'), compute="_compute_name")
    start_date = fields.Date(required=True)
    end_date = fields.Date(required=True)
    user_id = fields.Many2one("res.users", string="Responsible User", default=lambda self: self.env.user, required=True)
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one('res.currency', related="company_id.currency_id", required=True, readonly=False,
                                  string='Currency')
    cash_flow = fields.Float("Cash IN")
    cash_out = fields.Float("Cash Out")
    cash_balance = fields.Float("Cash Balance", compute="_compute_cash_amount")
    cash_out_line_ids = fields.One2many('petty.cash.out', 'petty_cash_id', string="Settlement")
    cash_issue_line_ids = fields.One2many('petty.cash.release', 'petty_cash_id', string="Petty Cash Out")
    cash_in_line_ids = fields.One2many('petty.cash.in', 'petty_cash_id', string="Petty Cash IN")
    journal_id = fields.Many2one('account.journal', string='Journal', required=True, readonly=True,
                                 states={'draft': [('readonly', False)]}, domain="[('is_petty_cash','=', True)]")
    is_transferred = fields.Boolean(default=False)
    state = fields.Selection([
                            ('draft', 'Draft'),
                            ('in_progress', 'In Progress'),
                            ('complete', 'completed'),
                            ('balance', 'Balanced')], string="State", default="draft", tracking=True)
    move_id = fields.Many2many('account.move', string="Journal Entries", copy=False)

    petty_cash_line_ids = fields.One2many('petty.cash.line', 'petty_cash_id', string="Transactions")

    def _compute_name(self):
        """Generate name for records"""
        for rec in self:
            name = "New"
            if rec.start_date and rec.end_date:
                journal_name = rec.journal_id.name if rec.journal_id else " "
                name = journal_name + " - " + str(rec.start_date) + " To " + str(rec.end_date)
            rec.name = name

    @api.depends('cash_in_line_ids')
    def _compute_cash_amount(self):
        """Compute cash out and balanced amount"""
        for rec in self:
            rec.cash_balance = rec.cash_flow - rec.cash_out

    @api.onchange('journal_id')
    def _onchange_journal_id(self):
        """Change start and end date when change the journal id"""
        date_range = self.env['ir.config_parameter'].sudo().get_param('petty_cash.petty_cash_date_range') or False
        if self.journal_id:
            petty_cashes = self.env['petty.cash'].search([('journal_id', '=', self.journal_id.id)], order="end_date desc", limit=1)

            if petty_cashes:
                start_date = petty_cashes.end_date + timedelta(days=1)
                self.start_date = start_date
                if not date_range:
                    date_range = 30
                else:
                    date_range = int(date_range)
                self.end_date = start_date + timedelta(days=date_range)
            else:
                start_date = datetime.today().date()
                self.start_date = start_date
                if not date_range:
                    date_range = 30
                else:
                    date_range = int(date_range)
                self.end_date = start_date + timedelta(days=date_range)
        else:
            start_date = datetime.today().date()
            self.start_date = start_date
            if not date_range:
                date_range = 30
            else:
                date_range = int(date_range)
            self.end_date = start_date + timedelta(days=date_range)

    def button_confirm_petty_cash(self):
        """Confirm Petty cash Flow"""
        self.ensure_one()
        self.state = 'in_progress'



    def button_petty_cash_iou_request(self):
        """Create Cash release for petty cash"""
        self.ensure_one()
        context = self.env.context.copy()
        context.update({'default_petty_cash_id':self.id, 'default_is_wizard': True})
        view_id = self.env.ref('petty_cash.view_petty_cash_release_form').id
        return {'type': 'ir.actions.act_window',
                'name': _('IOU Request'),
                'res_model': 'petty.cash.release',
                'target': 'new',
                'view_mode': 'form',
                'views': [[view_id, 'form']],
                'context': context,
                }

    def action_button_petty_cash_in(self):
        """Create Cash IN for petty cash"""
        self.ensure_one()
        context = self.env.context.copy()
        context.update({'default_petty_cash_id': self.id, 'create': False})
        action = self.env.ref('petty_cash.action_petty_cash_in_by_petty_cash').read()[0]
        action['domain'] = [('id', 'in', self.cash_in_line_ids.ids)]
        action['view_mode'] = 'tree,form'
        action['context'] = context
        return action

    def action_button_iou_requests(self):
        """Create Cash IOU Requests for petty cash"""
        self.ensure_one()
        context = self.env.context.copy()
        context.update({'default_petty_cash_id': self.id, 'create': False})
        action = self.env.ref('petty_cash.action_iou_request_by_petty_cash').read()[0]
        action['domain'] = [('petty_cash_id', '=', self.id)]
        action['view_mode'] = 'tree,form'
        action['context'] = context
        return action

    def action_button_reimbursement(self):
        """Create Cash Reimbursement for petty cash"""
        self.ensure_one()
        context = self.env.context.copy()
        context.update({'default_petty_cash_id': self.id, 'create': False})
        action = self.env.ref('petty_cash.action_petty_cash_out').read()[0]
        action['domain'] = [('petty_cash_id', '=', self.id)]
        action['view_mode'] = 'tree,form'
        action['context'] = context
        return action

    def button_petty_cash_in(self):
        """Create Cash IN for petty cash"""
        context = self.env.context.copy()
        context.update({'default_petty_cash_id': self.id, 'default_is_wizard': True})
        view_id = self.env.ref('petty_cash.view_petty_cash_in_form').id
        return {'type': 'ir.actions.act_window',
                'name': _('Top Up'),
                'res_model': 'petty.cash.in',
                'target': 'new',
                'view_mode': 'form',
                'views': [[view_id, 'form']],
                'context': context,
                }

    def button_petty_reimbursement(self):
        """create Reimbursement for petty cash"""
        self.ensure_one()
        context = self.env.context.copy()
        context.update({'default_petty_cash_id':self.id, 'default_is_wizard': True})
        view_id = self.env.ref('petty_cash.view_petty_cash_out_form').id
        return {'type': 'ir.actions.act_window',
                'name': _('Petty Cash Out'),
                'res_model': 'petty.cash.out',
                'target': 'new',
                'view_mode': 'form',
                'views': [[view_id, 'form']],
                'context': context,
                }


    def button_view_journal_entries(self):
        """view journal entries related to this"""
        self.ensure_one()
        context = self.env.context.copy()
        context.update({'create': False})
        action = self.env.ref('account.action_move_journal_line').read()[0]
        action['domain'] = [('id', 'in', self.move_id.ids)]
        action['view_mode'] = 'form'
        action['context'] = context
        return action

    def button_petty_cash_complete(self):
        """functions for confirm petty cash balanced"""
        self.ensure_one()

        self.ensure_one()
        for cash_in in self.cash_in_line_ids:
            if cash_in.state not in ('toppedup', 'reject', 'draft'):
                raise ValidationError(" (%s) - TopUp is not  toppedup or rejected " % cash_in.name)

        for iou in self.cash_issue_line_ids:
            if iou.state not in ('complete', 'reject', 'draft'):
                raise ValidationError(" (%s) - IOU Request is not completed or rejected " % iou.name)

        for cash_out in self.cash_out_line_ids:
            if cash_out.state not in ('complete', 'reject', 'draft'):
                raise ValidationError(" (%s) - Reimbursement is not completed or rejected " % cash_out.name)

        # CHECK IS THERE A CASH IN THE SELECTED JOURNAL
        if self.cash_balance == 0.00:
            self.state = 'complete'
        else:
            context = self.env.context.copy()
            context.update({
                'default_petty_cash_id': self.id,
                'default_journal_id': self.journal_id.id,
                'default_cash_balance': self.cash_balance,
            })
            view_id = self.env.ref('petty_cash.petty_cash_balance_wizard_form').id
            return {'type': 'ir.actions.act_window',
                    'name': _('Petty Cash Balance'),
                    'res_model': 'petty.cash.balance.wizard',
                    'target': 'new',
                    'view_mode': 'form',
                    'views': [[view_id, 'form']],
                    'context': context,
                    }

    def create_new_petty_cash_flow(self):
        """Create next petty cash"""
        date_range = self.env['ir.config_parameter'].sudo().get_param('petty_cash.petty_cash_date_range') or False
        petty_cash_val = {
            'start_date': self.end_date + timedelta(days=1),
            'end_date': self.end_date + timedelta(days=1 + int(date_range) if date_range else 30),
            'journal_id': self.journal_id.id,
            'currency_id': self.currency_id.id,
            'company_id': self.company_id.id,
            'user_id': self.env.user.id
        }
        petty_cash = self.env['petty.cash'].create(petty_cash_val)
        if not self.is_transferred and self.cash_balance > 0.00:
            vals={
                'petty_cash_id': petty_cash.id,
                'request_date': fields.Datetime.now(),
                'cash_date': fields.Datetime.now(),
                'amount': self.cash_balance,
                'reason': "From %s" % self.name,
                'state': "done",
            }
            petty_cash_in = self.env['petty.cash.in'].create(vals)
            petty_cash.write({
                'cash_in_line_ids': [(4, petty_cash_in.id)],
                'cash_flow': petty_cash_in.amount,
            })
        self.state = "balance"
        return {
            'name': _('Petty Cash'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_model': 'petty.cash',
            'target': 'current',
            'res_id': petty_cash.id,
            'domain': [('id', '=', petty_cash.id)],
        }


class PettyCashLine(models.Model):
    _name = "petty.cash.line"
    _description = "Petty Cash Lines"
    _order = 'create_date desc'

    name = fields.Char(required=True, string="number")
    petty_cash_id = fields.Many2one('petty.cash', string='Petty cash Drawer')
    from_acc = fields.Many2one('account.account', string="Source")
    to_acc = fields.Many2one('account.account', string="Destination")
    reason = fields.Char(string="Reason")
    amount = fields.Float(string="Amount")
    type = fields.Selection([('topup', 'Top-Up'), ('iou_request', 'IOU Request'), ('reimbursement', 'Reimbursement'), ('balance', 'balance')], default="topup")

    employee_id = fields.Many2one('hr.employee', string="Employee To")
    approved_by = fields.Many2one('res.users', string="Approved By")
    user_id = fields.Many2one('res.users', string="User")
    petty_cash_in = fields.Many2one('petty.cash.in', string="TopUp")
    cash_release_id = fields.Many2one('petty.cash.release', string="IOU Request")
    cash_reimbursement_id = fields.Many2one('petty.cash.out', string="Reimbursements")
