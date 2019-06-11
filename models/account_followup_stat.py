# -*- coding: utf-8 -*-
# Copyright 2004-2010 Tiny SPRL (<http://tiny.be>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, tools
from odoo import fields, models


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
        'account_followup.followup.line', 'Follow Ups', readonly=True,
        ondelete="cascade")
    balance = fields.Float('Balance', readonly=True)
    debit = fields.Float('Debit', readonly=True)
    credit = fields.Float('Credit', readonly=True)
    company_id = fields.Many2one('res.company', 'Company', readonly=True)
    blocked = fields.Boolean('Blocked', readonly=True)

    # TODO: do something with OCA account_fiscal_year or date_range modules
    # def search(self, args, offset=0, limit=None, order=None,
    #             context=None, count=False):
    #     for arg in args:
    #         if arg[0] == 'period_id' and arg[2] == 'current_year':
    #             current_year = self.env['account.fiscalyear'].find(cr, uid)
    #             ids = self.env['account.fiscalyear'].read(
    #                 [current_year], ['period_ids'])[0]['period_ids']
    #             args.append(['period_id','in',ids])
    #             args.remove(arg)
    #     return super(AccountFollowupStat, self).search(
    #         args=args, offset=offset, limit=limit, order=order,
    #         context=context, count=count)
    #
    # def read_group(self, domain, *args, **kwargs):
    #     for arg in domain:
    #         if arg[0] == 'period_id' and arg[2] == 'current_year':
    #             current_year = self.env['account.fiscalyear'].find(cr, uid)
    #             ids = self.env['account.fiscalyear'].read(
    #                 [current_year], ['period_ids'])[0]['period_ids']
    #             domain.append(['period_id','in',ids])
    #             domain.remove(arg)
    #     return super(AccountFollowupStat, self).read_group(
    #         domain, *args, **kwargs)

    @api.model_cr
    def init(self):
        tools.drop_view_if_exists(self._cr, 'account_followup_stat')
        self._cr.execute("""
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
