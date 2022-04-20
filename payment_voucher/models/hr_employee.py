from odoo import fields, api, models


class Employee(models.Model):
    _inherit = 'hr.employee'

    partner_id = fields.Many2one('res.partner', string='Related Partner')

    # function for create partner from employee
    def create_partner(self):
        # Create the Partner for the new employee
        partner = self.env['res.partner'].create({'name': self.name,
                                                  'phone': self.work_phone,
                                                  'mobile': self.mobile_phone,
                                                  'email': self.work_email,
                                                  'company_id': self.company_id.id})
        self.sudo().write({
            'partner_id': partner.id
        })
