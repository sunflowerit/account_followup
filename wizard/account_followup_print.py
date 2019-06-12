# -*- coding: utf-8 -*-
# Copyright 2004-2010 Tiny SPRL (<http://tiny.be>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import datetime
import time

from odoo import fields, models, api
from odoo.tools.translate import _


class AccountFollowupPrint(models.TransientModel):
    _name = 'account_followup.print'
    _description = 'Print Follow-up & Send Mail to Customers'

    def _get_followup(self):
        if self.env.context.get('active_model') == 'account_followup.followup':
            return self.env.context.get('active_id', False)
        return self.env['account_followup.followup'].search([
            ('company_id', '=', self.env.user.company_id.id)
        ])[:1]

    date = fields.Date(
        'Follow-up Sending Date', required=True,
        help="This field allow you to select a forecast date to plan your "
        "follow-ups", default=lambda *a: time.strftime('%Y-%m-%d'))
    followup_id = fields.Many2one(
        'account_followup.followup', 'Follow-Up', required=True,
        readonly=True, default=_get_followup)
    partner_ids = fields.Many2many(
        'account_followup.stat.by.partner', 'partner_stat_rel',
        'osv_memory_id', 'partner_id', 'Partners', required=True)
    company_id = fields.Many2one(
        related='followup_id.company_id', relation='res.company',
        store=True, readonly=True)
    email_conf = fields.Boolean('Send Email Confirmation')
    email_subject = fields.Char(
        'Email Subject', size=64, default=_('Invoices Reminder'))
    partner_lang = fields.Boolean(
        'Send Email in Partner Language',
        help='Do not change message text, if you want to send email in partner'
        ' language, or configure from company', default=True)
    email_body = fields.Text('Email Body', default="")
    summary = fields.Text('Summary', readonly=True)
    test_print = fields.Boolean(
        'Test Print',
        help='Check if you want to print follow-ups without changing '
        'follow-up level.')
    
    def process_partners(self, partner_ids, data):
        partner_obj = self.env['res.partner']
        partner_ids_to_print = []
        nbmanuals = 0
        manuals = {}
        nbmails = 0
        nbunknownmails = 0
        nbprints = 0
        size = 80
        resulttext = "<div style='height:{}px'>"
        for this in self.env['account_followup.stat.by.partner'].browse(
                partner_ids):
            if this.max_followup_id.manual_action:
                this.do_partner_manual_action()
                nbmanuals = nbmanuals + 1
                key = this.partner_id.payment_responsible_id.name or \
                      _("Anybody")
                if key not in manuals:
                    manuals[key] = 1
                else:
                    manuals[key] += 1
            if this.max_followup_id.send_email:
                this.partner_id.do_partner_mail()
                nbmails += 1
            if this.max_followup_id.send_letter:
                partner_ids_to_print.append(this.id)
                nbprints += 1
                message = _("Follow-up letter of <I> %s </I> will be sent") % (
                    this.partner_id.latest_followup_level_id_without_lit.name,)
                this.message_post(body=message)
        if nbunknownmails == 0:
            resulttext += str(nbmails) + _(" email(s) sent")
        else:
            resulttext += \
                str(nbmails) + \
                _(" email(s) should have been sent, but ") + \
                str(nbunknownmails) + \
                _(" had unknown email address(es)") + "\n <BR/> "
        resulttext += \
            "<BR/>" + \
            str(nbprints) + \
            _(" letter(s) in report") + \
            " \n <BR/>" + \
            str(nbmanuals) + \
            _(" manual action(s) assigned:")
        needprinting = False
        if nbprints > 0:
            needprinting = True
        resulttext += "<p align=\"center\">"
        for item in manuals:
            resulttext += "<li>{}: {}\n</li>".format(
                item, str(manuals[item]))
            size += 20
        resulttext += "</p></div>"
        result = {}
        resulttext = resulttext.format(size)
        action = partner_obj.do_partner_print(partner_ids_to_print, data)
        result['needprinting'] = needprinting
        result['resulttext'] = resulttext
        result['action'] = action or {}
        return result

    def do_update_followup_level(self, to_update, partner_list, date):
        # update the follow-up level on account.move.line
        for id in to_update.keys():
            if to_update[id]['partner_id'] in partner_list:
                line = self.env['account.move.line'].browse(int(id))
                line.followup_line_id = to_update[id]['level']
                line.followup_date = date
                #self.env['account.move.line'].write([int(id)], {'followup_line_id': to_update[id]['level'], 'followup_date': date})

    @api.model
    def clear_manual_actions(self, partner_ids):
        # Partnerlist is list to exclude
        # Will clear the actions of partners that have no due payments anymore
        stat_obj = self.env['account_followup.stat.by.partner']
        partner_list_ids = stat_obj.browse(partner_ids).mapped(
            'partner_id').ids
        if not partner_list_ids:
            partner_list_ids = [-1]
        partner_ids = self.env['res.partner'].search([
            '&', ('id', 'not in', partner_list_ids), '|',
            ('payment_responsible_id', '!=', False),
            ('payment_next_action_date', '!=', False)
        ])

        partners_to_clear = []
        for part in partner_ids:
            if not part.unreconciled_aml_ids: 
                partners_to_clear.append(part.id)
                part.action_done()
        return len(partners_to_clear)

    @api.multi
    def do_process(self):
        context = dict(self.env.context or {})

        # Get partners
        tmp = self._get_partners_followup()
        partners = self.env['res.partner'].browse(tmp['partner_ids'])
        to_update = tmp['to_update']
        date = self.date
        data = {
            "date": self.date,
            "followup_id": self.followup_id.id,
        }

        # Update partners
        self.do_update_followup_level(to_update, partners.ids, date)
        # process the partners (send mails...)
        restot_context = context.copy()
        restot = self.process_partners(partners.ids, data)
        context.update(restot_context)
        # clear the manual actions if nothing is due anymore
        nbactionscleared = self.clear_manual_actions(partners.ids)
        if nbactionscleared > 0:
            restot['resulttext'] = \
                restot['resulttext'] + \
                "<li>" + \
                _("%s partners have no credits and as such the action is "
                  "cleared") %(str(nbactionscleared)) + "</li>"
        view_id = self.env.ref(
            'account_followup.view_account_followup_sending_results').id
        context.update({
            'description': restot['resulttext'],
            'needprinting': restot['needprinting'],
            'report_data': restot['action']
        })
        return {
            'name': _('Send Letters and Emails: Actions Summary'),
            'view_type': 'form',
            'context': context,
            'view_mode': 'tree,form',
            'res_model': 'account_followup.sending.results',
            'views': [(view_id, 'form')],
            'type': 'ir.actions.act_window',
            'target': 'new',
            }

    def _get_msg(self):
        return self.env['res.users'].browse(self.env.user).company_id.follow_up_msg

    def _get_partners_followup(self):

        company_id = self.company_id.id

        self.env.cr.execute(
            "SELECT l.partner_id, l.followup_line_id,l.date_maturity, l.date, l.id "\
            "FROM account_move_line AS l "\
                "LEFT JOIN account_account AS a "\
                "ON (l.account_id=a.id) "\
            "WHERE (l.full_reconcile_id IS NULL) "\
                "AND (a.user_type_id=1) "\
                "AND (l.partner_id is NOT NULL) "\
                "AND (l.debit > 0) "\
                "AND (l.company_id = %s) " \
                "AND (l.blocked = False)" \
            "ORDER BY l.date", (company_id,))  #l.blocked added to take litigation into account and it is not necessary to change follow-up level of account move lines without debit
        move_lines = self.env.cr.fetchall()
        old = None
        fups = {}
        fup_id = 'followup_id' in self.env.context and self.env.context['followup_id'] or self.followup_id.id
        date = 'date' in self.env.context and self.env.context['date'] or self.date

        current_date = datetime.date(*time.strptime(date,
            '%Y-%m-%d')[:3])
        self.env.cr.execute(
            "SELECT * "\
            "FROM account_followup_followup_line "\
            "WHERE followup_id=%s "\
            "ORDER BY delay", (fup_id,))
        
        #Create dictionary of tuples where first element is the date to compare with the due date and second element is the id of the next level
        for result in self.env.cr.dictfetchall():
            delay = datetime.timedelta(days=result['delay'])
            fups[old] = (current_date - delay, result['id'])
            old = result['id']

        partner_list = []
        to_update = {}
        # Fill dictionary of accountmovelines to_update with the partners
        # that need to be updated
        for partner_id, followup_line_id, date_maturity,date, id in move_lines:
            if not partner_id:
                continue
            if followup_line_id not in fups:
                continue
            stat_line_id = partner_id * 10000 + company_id
            if date_maturity:
                if date_maturity <= fups[followup_line_id][0].strftime('%Y-%m-%d'):
                    if stat_line_id not in partner_list:
                        partner_list.append(stat_line_id)
                    to_update[str(id)]= {'level': fups[followup_line_id][1], 'partner_id': stat_line_id}
            elif date and date <= fups[followup_line_id][0].strftime('%Y-%m-%d'):
                if stat_line_id not in partner_list:
                    partner_list.append(stat_line_id)
                to_update[str(id)]= {'level': fups[followup_line_id][1], 'partner_id': stat_line_id}
        return {'partner_ids': partner_list, 'to_update': to_update}
