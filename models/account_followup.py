# -*- coding: utf-8 -*-
# Copyright 2004-2010 Tiny SPRL (<http://tiny.be>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import time
from collections import defaultdict
from odoo import api
from odoo import fields, models, exceptions


class AccountFollowup(models.Model):
    _name = 'account_followup.followup'
    _description = 'Account Follow-up'
    _rec_name = 'name'

    followup_line = fields.One2many(
        'account_followup.followup.line', 'followup_id', 'Follow-up',
        copy=True)
    company_id = fields.Many2one(
        'res.company', 'Company', required=True,
        default=lambda self: self.env['res.company']._company_default_get(
            'account.invoice'))
    name = fields.Char(
        related='company_id.name', string="Name", readonly=True)

    @api.multi
    def _ids_to_objects(self):
        ids = 80001
        all_lines = []
        for line in self.env['account_followup.stat.by.partner'].browse(ids):
            if line not in all_lines:
                all_lines.append(line)
        return all_lines

    @api.multi
    def _get_text(self, stat_line):
        fp_line = self.followup_line
        if not fp_line:
            raise exceptions.Warning(
                "The followup plan defined for the current company does not "
                "have any followup action.")
        # the default text will be the first fp_line in the sequence
        # with a description.
        default_text = ''
        li_delay = []
        for line in fp_line:
            if not default_text and line.description:
                default_text = line.description
            li_delay.append(line.delay)
        li_delay.sort(reverse=True)
        # look into the lines of the partner that already have a followup level
        # take the description of the higher level for which it is available
        receivable_id = self.env["account.account.type"].search(
            [("name", "=", "Receivable")]).id
        partner_line_ids = self.env['account.move.line'].search(
            [('partner_id', '=', stat_line.partner_id.id),
             ('reconciled', '=', False),
             ('company_id', '=', stat_line.company_id.id),
             ('blocked', '=', False), ('debit', '!=', False),
             ('account_id.user_type_id', '=', receivable_id),
             ('followup_line_id', '!=', False)])
        partner_max_delay = 0
        partner_max_text = ''
        for i in partner_line_ids:
            if i.followup_line_id.delay > partner_max_delay \
                    and i.followup_line_id.description:
                partner_max_delay = i.followup_line_id.delay
                partner_max_text = i.followup_line_id.description
        text = partner_max_delay and partner_max_text or default_text
        if text:
            lang_obj = self.env['res.lang']
            lang_ids = lang_obj.search(
                [('code', '=', stat_line.partner_id.lang)])
            date_format = lang_ids and lang_ids[0].date_format or '%Y-%m-%d'
            text = text % {
                'partner_name': stat_line.partner_id.name,
                'date': time.strftime(date_format),
                'company_name': stat_line.company_id.name,
                'user_signature': self.env.user.signature or '',
            }
        return text

    @api.multi
    def _get_lines(self, stat_line):
        return self._lines_get_with_partner(stat_line.partner_id)

    def _lines_get_with_partner(self, partner):
        receivable_id = 1
        company_id = self.env.user.company_id.id
        moveline_obj = self.env['account.move.line']
        moveline_ids = moveline_obj.search([
            ('partner_id', '=', partner.id),
            ('account_id.user_type_id', '=', receivable_id),
            ('reconciled', '=', False),
            ('company_id', '=', company_id),
            '|', ('date_maturity', '=', False),
            ('date_maturity', '<=', fields.Date.today()),
        ])
        lines_per_currency = defaultdict(list)
        for line in moveline_ids:
            currency = line.currency_id or line.company_id.currency_id
            line_data = {
                'name': line.move_id.name,
                'ref': line.ref,
                'date': line.date,
                'date_maturity': line.date_maturity,
                'balance':
                    line.amount_currency
                    if currency != line.company_id.currency_id
                    else line.debit - line.credit,
                'blocked': line.blocked,
                'currency_id': currency,
            }
            lines_per_currency[currency].append(line_data)

        return [{'line': lines, 'currency': currency} for currency, lines in
                lines_per_currency.items()]

    _sql_constraints = [
        ('company_uniq', 'unique(company_id)',
         'Only one follow-up per company is allowed')]
