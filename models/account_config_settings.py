# -*- coding: utf-8 -*-
# Copyright 2004-2010 Tiny SPRL (<http://tiny.be>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import time
from collections import defaultdict
from odoo import api, tools
from odoo import fields, models, exceptions


class AccountConfigSettings(models.TransientModel):
    _name = 'account.config.settings'
    _inherit = 'account.config.settings'

    # TODO: this needs Enterprise!
    def open_followup_level_form(self):
        res_ids = self.env['account_followup.followup'].search([])
        
        return {
                 'type': 'ir.actions.act_window',
                 'name': 'Payment Follow-ups',
                 'res_model': 'account_followup.followup',
                 'res_id': res_ids and res_ids[0] or False,
                 'view_mode': 'form,tree',
         }
