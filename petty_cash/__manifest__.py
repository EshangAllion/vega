{
    'name': 'Petty Cash',
    'version': '1.0',
    'sequence': 1,
    'author': "Centrics Business Solutions (Pvt) Ltd",
    'website': 'http://www.centrics.cloud/',
    'summary': 'Manage process of Petty cash',
    'description': """Manage process of Petty cash""",
    'depends': ['base', 'utm', 'account', 'account_accountant', 'hr'],
    'data': [
        'data/mail_template.xml',
        'data/ir_sequence.xml',

        'reports/cash_out_payment_voucher.xml',
        'reports/reimbursement_payment_voucher.xml',

        'security/security.xml',
        'security/access_rules.xml',
        'security/ir.model.access.csv',

        'wizard/reject_reason_view.xml',

        'views/res_config_settings_view.xml',
        'views/petty_cash_views.xml',
        'views/reimbursements_views.xml',
        'views/petty_cash_topup_views.xml',
        'views/petty_cash_reason_view.xml',
        'views/iou_request_views.xml',
        'views/account_journal_view.xml',
        'views/hr_employee_view.xml',
        'views/menuitem.xml',

        'wizard/approve_user_view.xml',
        'wizard/approved_with_coment_wizard_view.xml',
        'wizard/petty_cash_balance_wizard_view.xml',
        'wizard/multi_reimbursement_request_approval_view.xml',
        'wizard/multi_cash_out_approval_view.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
