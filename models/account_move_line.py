# -*- coding: utf-8 -*-
# Copyright 2004-2010 Tiny SPRL (<http://tiny.be>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import time
from collections import defaultdict
from odoo import api, tools
from odoo import fields, models, exceptions


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.one
    @api.depends('debit', 'credit')
    def _get_result(self):
        self.result = self.debit - self.credit

    followup_line_id = fields.Many2one(
        'account_followup.followup.line', 'Follow-up Level',
        ondelete='restrict')  # restrict deletion of the followup line
    followup_date = fields.Date('Latest Follow-up', index=True)
    
    result = fields.Float(
        compute="_get_result", method=True, string="Balance")
