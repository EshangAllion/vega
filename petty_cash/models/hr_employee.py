# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, AccessError


class HrEmployee(models.Model):
    """
    Inherit employee model
    """
    _inherit = "hr.employee"

    issued_petty_cash = fields.Float(string="Total Issued",  compute="compute_petty_cash_balance")
    expensed_petty_cash = fields.Float(string="Total Expensed",  compute="compute_petty_cash_balance")
    pay_to_employee = fields.Float(string="Pay to Employee", compute="compute_pay_to_employee")
    pay_petty_cash = fields.Float(string="Pay to Employee", default=0.00)
    cash_issue_ids = fields.One2many('petty.cash.release', 'employee_id', string="Cash Release")
    cash_out_ids = fields.One2many('petty.cash.out', 'employee_id', string="Cash Out")

    def compute_petty_cash_balance(self):
        """
        Calculate petty cash out and petty cash in
        :return: issued petty cash(float)
        """
        for rec in self:
            issued_petty_cash = 0.00  # total issues
            expensed_petty_cash = 0.00

            # issued petty cash
            issues = self.env['petty.cash.release'].search([('employee_id', '=', rec.id), ('state', 'not in', ('draft', 'reject'))])
            for issue in issues:
                issued_petty_cash += issue.released_amount
                expensed_petty_cash += issue.expensed_amount
            # expensed petty cash
            expenses = self.env['petty.cash.out'].search([('employee_id', '=', rec.id), ('state', 'not in', ('draft', 'reject'))])
            for expense in expenses:
                expensed_petty_cash += expense.expensed_amount

            rec.issued_petty_cash = issued_petty_cash
            rec.expensed_petty_cash = expensed_petty_cash

    @api.depends('cash_issue_ids', 'cash_out_ids')
    def compute_pay_to_employee(self):
        """ Calculate pending cash from employee to company"""
        for rec in self:
            issues = 0.00
            expenses = 0.00
            # Find all IOU requests of cash issue to employee without reimbursement
            without_reim_issues = self.env['petty.cash.release'].search([('employee_id', '=', rec.id),
                                                                         ('balanced_amount', '>', 0.00),
                                                                         ('state', '=', 'released')])
            for without_reim in without_reim_issues:
                issues += without_reim.balanced_amount

            #  Find all reimbursements of expense by employee
            without_reim_issues = self.env['petty.cash.out'].search([('employee_id', '=', rec.id),
                                                                         ('expensed_amount', '>', 0.00),
                                                                         ('state', 'not in', ('complete','reject'))])
            for without_reim in without_reim_issues:
                expenses += without_reim.expensed_amount

            rec.pay_to_employee = expenses - issues
            rec.pay_petty_cash = expenses - issues

    def button_view_cash_issues(self):
        """Find all IOU requests related to employee"""
        self.ensure_one()
        context = self.env.context.copy()
        action = self.env.ref('petty_cash.action_petty_cash_release').read()[0]
        action['domain'] = [('employee_id', '=', self.id)]
        action['view_mode'] = 'form'
        action['context'] = context
        return action

    def button_view_cash_out(self):
        """Find all reimbursements related to employee"""
        self.ensure_one()
        context = self.env.context.copy()
        action = self.env.ref('petty_cash.action_petty_cash_out').read()[0]
        action['domain'] = [('employee_id', '=', self.id)]
        action['view_mode'] = 'form'
        action['context'] = context
        return action


