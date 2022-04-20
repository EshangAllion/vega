from odoo import fields, api, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    is_petty_cash = fields.Boolean("Petty Cash")
