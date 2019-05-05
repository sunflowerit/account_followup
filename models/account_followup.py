# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from odoo import api, tools
from odoo import fields, models


class AccountFollowup(models.Model):
    _name = 'account_followup.followup'
    _description = 'Account Follow-up'
    _rec_name = 'name'

    followup_line = fields.One2many(
        'account_followup.followup.line', 'followup_id', 'Follow-up', copy=True)
    company_id = fields.Many2one(
        'res.company', 'Company', required=True,
        default=lambda self: self.env['res.company']._company_default_get(
            'account.invoice'))
    name = fields.Char(
        related='company_id.name', string="Name", readonly=True)

    _sql_constraints = [
        ('company_uniq', 'unique(company_id)',
         'Only one follow-up per company is allowed')]


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


class AccountFollowupStat(models.Model):
    _name = "account_followup.stat"
    _description = "Follow-up Statistics"
    _rec_name = 'partner_id'
    _order = 'date_move'
    _auto = False

    partner_id = fields.Many2one('res.partner', 'Partner', readonly=True)
    date_move = fields.Date('First move', readonly=True)
    date_move_last = fields.Date('Last move', readonly=True)
    date_followup = fields.Date('Latest followup', readonly=True)
    followup_id = fields.Many2one(
        'account_followup.followup.line' 'Follow Ups', readonly=True,
        ondelete="cascade")
    balance = fields.Float('Balance', readonly=True)
    debit = fields.Float('Debit', readonly=True)
    credit = fields.Float('Credit', readonly=True)
    company_id = fields.Many2one('res.company', 'Company', readonly=True)
    blocked = fields.Boolean('Blocked', readonly=True)
    period_id = fields.Many2one('account.period', 'Period', readonly=True)

    def search(self, args, offset=0, limit=None, order=None,
                context=None, count=False):
        for arg in args:
            if arg[0] == 'period_id' and arg[2] == 'current_year':
                current_year = self.env['account.fiscalyear'].find(cr, uid)
                ids = self.env['account.fiscalyear'].read([current_year], ['period_ids'])[0]['period_ids']
                args.append(['period_id','in',ids])
                args.remove(arg)
        return super(AccountFollowupStat, self).search(args=args, offset=offset, limit=limit, order=order,
            context=context, count=count)

    def read_group(self, domain, *args, **kwargs):
        for arg in domain:
            if arg[0] == 'period_id' and arg[2] == 'current_year':
                current_year = self.env['account.fiscalyear'].find(cr, uid)
                ids = self.env['account.fiscalyear'].read([current_year], ['period_ids'])[0]['period_ids']
                domain.append(['period_id','in',ids])
                domain.remove(arg)
        return super(AccountFollowupStat, self).read_group(domain, *args, **kwargs)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'account_followup_stat')
        self.env.cr.execute("""
            create or replace view account_followup_stat as (
                SELECT
                    l.id as id,
                    l.partner_id AS partner_id,
                    min(l.date) AS date_move,
                    max(l.date) AS date_move_last,
                    max(l.followup_date) AS date_followup,
                    max(l.followup_line_id) AS followup_id,
                    sum(l.debit) AS debit,
                    sum(l.credit) AS credit,
                    sum(l.debit - l.credit) AS balance,
                    l.company_id AS company_id,
                    l.blocked as blocked
                FROM
                    account_move_line l
                    LEFT JOIN account_account a ON (l.account_id = a.id)
                WHERE
                    a.user_type_id = 1 AND
                    l.full_reconcile_id is NULL AND
                    l.partner_id IS NOT NULL
                GROUP BY
                    l.id, l.partner_id, l.company_id, l.blocked
            )""")

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
