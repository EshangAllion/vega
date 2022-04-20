from odoo import fields, models, api
from datetime import datetime
from datetime import timedelta


class PettyCashBalanceWizard(models.TransientModel):
    """
    petty cash balanced Wizard
    """
    _name = 'petty.cash.balance.wizard'
    _description = 'Cash balance'

    user_id = fields.Many2one('res.users', string="Approver", required=1, default=lambda self: self.env.user.id)
    journal_id = fields.Many2one('account.journal', string='Journal', )
    petty_cash_id = fields.Many2one('petty.cash', required=True, string="Petty Cash Drawer")
    cash_balance = fields.Float(string='Cash Balance')

    note = fields.Char("Note")
    return_journal = fields.Many2one('account.journal', string="Return Account", domain="[('type','in',('bank','cash'))]")

    def approval_submission(self):
        """balanced the petty cash """
        entry_vals = {
            'date': datetime.now().date(),
            'journal_id': self.journal_id.id,
            'ref': "Return petty cash balance - " + str(self.petty_cash_id.name),
            'company_id': int(self.petty_cash_id.company_id.id),
            'currency_id': int(self.petty_cash_id.currency_id.id),
            'line_ids': [
                (0, 0, {
                    'account_id': self.journal_id.default_account_id.id,
                    'name': "Return petty cash balance - " + str(self.petty_cash_id.name),
                    'credit': self.cash_balance,
                    'debit': 0.00,
                }),
                (0, 0, {
                    'account_id': self.return_journal.default_account_id.id,
                    'name': "Return petty cash balance - " + str(self.petty_cash_id.name),
                    'credit': 0.00,
                    'debit': self.cash_balance,
                })
            ]
        }
        journal_entry = self.env['account.move'].sudo().create(entry_vals)
        journal_entry.sudo().action_post()
        self.petty_cash_id.write({
            'move_id': [(4, journal_entry.id)],
            'is_transferred': True,
            'state': 'complete'
        })

        #   Create a log un relevant petty cash logins after finished
        self.env['petty.cash.line'].create({
            'name': self.petty_cash_id.name,
            'petty_cash_id': self.petty_cash_id.id,
            'from_acc': self.petty_cash_id.journal_id.default_account_id.id,
            'to_acc': self.return_journal.default_account_id.id,
            'reason': self.note,
            'amount': self.cash_balance,
            'type': 'balance',
            'user_id': self.user_id.id,
            'employee_id': False,
            'approved_by': False,
        })





