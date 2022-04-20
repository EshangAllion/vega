from datetime import datetime, timedelta
from functools import partial
from itertools import groupby

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.misc import formatLang, get_lang
from odoo.osv import expression
from odoo.tools import float_is_zero, float_compare
from collections import defaultdict
from odoo.tools.misc import clean_context
from odoo.http import request


class PaymentVoucher(models.Model):
    _name = 'payment.voucher'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin', 'utm.mixin']
    _description = 'Payment Voucher'

    @api.depends('voucher_lines.net_amount')
    def _amount_all(self):
        """
        Compute the total amounts of the lines.
        """
        for voucher in self:
            amount_total = 0.0
            for line in voucher.voucher_lines:
                amount_total += line.net_amount
            voucher.update({
                'amount': amount_total,
            })

    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.company)
    name = fields.Char('Payment Voucher No', copy=False)
    date = fields.Date('Date', default=fields.Date.context_today, tracking=True)
    cheque_no = fields.Char('Cheque No', tracking=True)
    cheque_date = fields.Date('Cheque Date', tracking=True)
    remarks = fields.Text('Remark', tracking=True)
    amount = fields.Monetary(string='Amount', store=True, readonly=True, compute='_amount_all')
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency', default=lambda self: self.env.company.currency_id.id, tracking=True)
    voucher_lines = fields.One2many('payment.voucher.line', 'voucher_id', string='Voucher Lines', copy=True,
                                    auto_join=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('waiting_approval', 'Waiting For Approval'),
        ('approved', 'Approved'),
        ('post', 'Posted'),
        ('cancel', 'Cancelled'),
    ], string='Status', readonly=True, copy=False, index=True, default='draft', tracking=True)
    journal_id = fields.Many2one('account.journal', string='Bank Account', required=True,
                                 check_company=True, domain="[('type', '=', 'bank')]", tracking=True)
    amount_in_words = fields.Char(string="Amount in Words", compute='_get_amount_in_words')
    custom_url = fields.Char("URL")
    approved_by = fields.Many2one('res.users', string="Approved/Rejected By", readonly=1, tracking=True)
    approve_Date = fields.Date(string="Approved/Rejected Date", readonly=1, tracking=True)
    comment = fields.Text(string="Approved/Rejected Comment", readonly=1, tracking=True)
    triggered_approval = fields.Boolean(string="Triggered Approval", default=False)
    partner_id = fields.Many2one(comodel_name='res.partner', string='Partner', tracking=True)

    def _get_amount_in_words(self):
        """Get amount in words"""
        for line in self:
            line.amount_in_words = str(line.currency_id.amount_to_text(line.amount))

    def view_je(self):
        """View related JE"""
        self.ensure_one()
        action = self.env.ref('account.action_move_journal_line').read()[0]
        action['domain'] = [('voucher_id', '=', self.id)]
        action['view_mode'] = 'tree'
        action['search_view_id'] = {}
        return action

    def action_post(self):
        first_approval = self.env['ir.config_parameter'].sudo().get_param(
            'payment_voucher.payment_voucher_approval')
        if first_approval:
            if not self.triggered_approval:
                model = self.env['ir.model'].search([('model', '=', request.params.get('model'))])
                return {
                    'name': _('Send to Approval'),
                    'type': 'ir.actions.act_window',
                    'view_mode': 'form',
                    'res_model': 'payment.voucher.approver.user.wizard',
                    'target': 'new',
                    'context': {'default_voucher_id': self.id,
                                'default_model_id': model.id}
                }

        entry_list = [(0, 0, {'debit': 0.0, 'credit': self.amount, 'date_maturity': False,
                              'account_id': self.journal_id.default_account_id.id, 'partner_id': False,
                              'currency_id': self.currency_id.id, 'name': self.name})]
        for debit in self.voucher_lines:
            entry_list.append((0, 0, {'debit': debit.net_amount, 'credit': 0.0, 'date_maturity': False,
                                      'account_id': debit.account_id.id, 'partner_id': debit.partner_id.id,
                                      'analytic_account_id': debit.analytic_account_id.id,
                                      'currency_id': self.currency_id.id, 'name': debit.label}))
        je = self.env['account.move'].create({
            'move_type': 'entry',
            'date': self.date,
            'journal_id': self.journal_id.id,
            'currency_id': self.currency_id.id,
            'ref': self.name,
            'line_ids': entry_list,
            'voucher_id': self.id
        })
        self.sudo().write({
            'state': 'post'
        })

        je.action_post()
        return True

    def action_cancel(self):
        move_obj = self.env['account.move'].search([('voucher_id', '=', self.id)])
        move_obj.button_cancel()

        self.sudo().write({
            'state': 'cancel',
            'triggered_approval': False,
        })
        return True

    def reset_draft(self):
        self.sudo().write({
            'state': 'draft',
            'triggered_approval': False,
        })

    def approve_transfer(self):
        model = self.env['ir.model'].search([('model', '=', request.params.get('model'))])
        return {
            'name': _('Comment'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'payment.voucher.approve.comment.wizard',
            'target': 'new',
            'context': {'default_voucher_id': self.id,
                        'default_model_id': model.id,
                        'default_action': self._context.get('action') or False,
                        }
        }

    def reject_transfer(self):
        model = self.env['ir.model'].search([('model', '=', request.params.get('model'))])
        return {
            'name': _('Comment'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'payment.voucher.approve.comment.wizard',
            'target': 'new',
            'context': {'default_voucher_id': self.id,
                        'default_model_id': model.id,
                        'default_action': self._context.get('action') or False,
                        }
        }

    @api.model
    def create(self, vals):
        """Call for the relates Voucher sequence and get the number to create the form"""
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('payment.voucher') or _('New')

        result = super(PaymentVoucher, self).create(vals)
        return result

    def unlink(self):
        """Cannot delete Posted and Cancelled Payment Vouchers"""
        if self.state == 'draft':
            return self.unlink()
        else:
            raise UserError('You can delete Draft Vouchers only.')


class PaymentVoucherLines(models.Model):
    _name = 'payment.voucher.line'

    voucher_id = fields.Many2one('payment.voucher', string='Voucher No', required=True, ondelete='cascade', index=True,
                                 copy=False)
    account_id = fields.Many2one(
        comodel_name='account.account',
        string='Account',
        domain="[]",
        check_company=True)
    label = fields.Char('Label')
    partner_id = fields.Many2one('res.partner', string='Partner')
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    net_amount = fields.Float('Net Amount')


class InheritAccountMove(models.Model):
    _inherit = ['account.move']

    voucher_id = fields.Many2one('payment.voucher', string='Voucher No')


