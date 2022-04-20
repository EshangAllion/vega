{
    'name': 'Payment Vouchers',
    'version': '1.0',
    'sequence': 1,
    'author': "Centrics Business Solutions PVT Ltd",
    'website': 'http://www.centrics.cloud/',
    'summary': """This module contains adding payment vouchers to the system with cheque printing""",
    'description': """This module contains adding payment vouchers to the system with cheque printing""",
    'depends': [
        'base', 'utm','mail', 'account', 'hr'
    ],
    'external_dependencies': {},
    'data': [
        'security/ir.model.access.csv',
        'security/record_rules.xml',
        'security/payment_voucher_security.xml',
        'data/ir_sequence_data.xml',
        'data/paperformat.xml',
        'data/mail_template.xml',
        'views/res_config_settings_views.xml',
        'views/payment_voucher_view.xml',
        'views/hr_employee_view.xml',
        'wizard/approve_user_view.xml',
        'wizard/approve_comment_view.xml',
        'reports/payament_voucher.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}

