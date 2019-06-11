# -*- coding: utf-8 -*-
# Copyright 2004-2010 Tiny SPRL (<http://tiny.be>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models, api


class AccountFollowupSendingResults(models.TransientModel):

    def do_report(self):
        return self.env.context.get('report_data')

    def do_done(self):
        return {}

    def _get_description(self):
        return self.env.context.get('description')

    def _get_need_printing(self):
        return self.env.context.get('needprinting')

    _name = 'account_followup.sending.results'
    _description = \
        'Results from the sending of the different letters and emails'

    description = fields.Text(
        "Description", readonly=True, default=_get_description)
    needprinting = fields.Boolean("Needs Printing", default=_get_need_printing)
