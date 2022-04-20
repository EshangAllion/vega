from odoo import models, fields, api, _


class PettyCashReasons(models.Model):
    """
    Petty cash Reasons Handling class
    """
    _name = "petty.cash.reason"
    _description = "Petty Cash reason"

    name = fields.Char(required=True)