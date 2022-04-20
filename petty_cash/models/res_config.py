# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    """Inherit configurations settings class"""
    _inherit = 'res.config.settings'

    petty_cash_date_range = fields.Integer(string="Patty Cash Date Range",  help="No of Days", default=30, config_parameter="petty_cash.petty_cash_date_range")
    minimum_amount_for_petty_cash = fields.Integer(string="Maximum Amount",  help="If employee's expenses more than minimum amount, Manager must approve", default=0, config_parameter="petty_cash.minimum_amount_for_petty_cash")
