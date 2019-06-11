# -*- coding: utf-8 -*-
# Copyright 2004-2010 Tiny SPRL (<http://tiny.be>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo import tools
from odoo import fields, models, api


class AccountFollowupStatByPartner(models.Model):
    _name = "account_followup.stat.by.partner"
    _description = "Follow-up Statistics by Partner"
    _rec_name = 'partner_id'
    _auto = False

    @api.model
    @api.depends('partner_id')
    def _compute_invoice_partner_id(self):
        for this in self:
            this.invoice_partner_id = this.partner_id.address_get(
                adr_pref=['invoice']).get('invoice', this.partner_id.id)

    partner_id = fields.Many2one('res.partner', 'Partner', readonly=True)
    date_move = fields.Date('First move', readonly=True)
    date_move_last = fields.Date('Last move', readonly=True)
    date_followup = fields.Date('Latest follow-up', readonly=True)
    max_followup_id = fields.Many2one(
        'account_followup.followup.line', 'Max Follow Up Level',
        readonly=True, ondelete='cascade')
    balance = fields.Float('Balance', readonly=True)
    company_id = fields.Many2one('res.company', 'Company', readonly=True)
    invoice_partner_id = fields.Many2one(
        'res.partner', compute='_compute_invoice_partner_id',
        string='Invoice Address')

    def init(self):
        tools.drop_view_if_exists(
            self.env.cr, 'account_followup_stat_by_partner')
        # Here we don't have other choice but to create a virtual ID based on
        # the concatenation of the partner_id and the company_id, because if a
        # partner is shared between 2 companies, we want to see 2 lines for him
        # in this table. It means that both companies should be able to send
        # him follow-ups separately. An assumption that the number of companies
        # will not reach 10 000 records is made, what should be enough
        # for a time.
        self.env.cr.execute("""
            create view account_followup_stat_by_partner as (
                SELECT
                    l.partner_id * 10000::bigint + l.company_id as id,
                    l.partner_id AS partner_id,
                    min(l.date) AS date_move,
                    max(l.date) AS date_move_last,
                    max(l.followup_date) AS date_followup,
                    max(l.followup_line_id) AS max_followup_id,
                    sum(l.debit - l.credit) AS balance,
                    l.company_id as company_id
                FROM
                    account_move_line l
                    LEFT JOIN account_account a ON (l.account_id = a.id)
                WHERE
                    a.user_type_id = 1 AND
                    l.full_reconcile_id is NULL AND
                    l.partner_id IS NOT NULL
                    GROUP BY
                    l.partner_id, l.company_id
            )
        """)
