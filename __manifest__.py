# -*- coding: utf-8 -*-
{
    'name': 'Payment Follow-up Management',
    'version': '10.0.1.0.0',
    'category': 'Accounting & Finance',
    'author': 'OpenERP SA, Sunflower IT',
    'website': 'https://www.odoo.com/page/billing',
    'summary': 'Module to automate letters for unpaid invoices',
    'depends': [
        'account',
        'account_accountant',
        'mail',
        'sale',
    ],
    'data': [
        # 'security/account_followup_security.xml',
        # 'security/ir.model.access.csv',
        'report/account_followup_report.xml',
        'report/report_followup.xml',
        'data/account_followup_data.xml',
        'views/account_followup_view.xml',
        'views/account_followup_customers.xml',
        'views/res_config_view.xml',
        'wizard/account_followup_print_view.xml',
    ],
    'demo': [
        'demo/account_followup_demo.xml'
    ],
    'test': [
        'test/account_followup.yml',
    ],
    'installable': True,
}
