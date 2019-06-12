# -*- coding: utf-8 -*-
# Copyright 2004-2010 Tiny SPRL (<http://tiny.be>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models, api, _
from odoo import exceptions
from collections import defaultdict
from odoo.tools.misc import formatLang


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model
    @api.depends('unreconciled_aml_ids')
    def _get_latest(self):
        company = self.env.user.company_id
        for this in self:
            latest_date = False
            latest_level = False
            latest_days = False
            latest_level_without_lit = False
            latest_days_without_lit = False
            for aml in this.unreconciled_aml_ids:
                if aml.company_id != company:
                    continue
                if aml.followup_line_id and (
                        not latest_days
                        or latest_days < aml.followup_line_id.delay):
                    latest_days = aml.followup_line_id.delay
                    latest_level = aml.followup_line_id.id
                if not latest_date or latest_date < aml.followup_date:
                    latest_date = aml.followup_date
                if not aml.blocked and aml.followup_line_id and (
                            not latest_days_without_lit
                            or latest_days_without_lit <
                            aml.followup_line_id.delay
                        ):
                    latest_days_without_lit = aml.followup_line_id.delay
                    latest_level_without_lit = aml.followup_line_id.id
            this.latest_followup_date = latest_date
            this.latest_followup_level_id = latest_level
            this.latest_followup_level_id_without_lit = \
                latest_level_without_lit

    @api.multi
    def do_partner_manual_action(self):
        for this in self:
            if this.payment_next_action:
                action_text = "{}\n{}".format(
                    this.payment_next_action or '',
                    this.latest_followup_level_id_without_lit
                    .manual_action_note or ''
                )
            else:
                action_text = \
                    this.latest_followup_level_id_without_lit \
                    .manual_action_note or ''

            # Check date: only change when it did not exist already
            action_date = this.payment_next_action_date \
                or fields.Date.context_today(self)

            # Check responsible: if partner has not got a responsible
            # already, take from follow-up
            if this.payment_responsible_id:
                responsible_id = this.payment_responsible_id
            else:
                p = this.latest_followup_level_id_without_lit \
                    .manual_action_responsible_id
                responsible_id = p and p.id or False
            this.payment_next_action_date = action_date
            this.payment_next_action = action_text
            this.payment_responsible_id = responsible_id

    def do_partner_print(self, wizard_partner_ids, data):
        # wizard_partner_ids are ids from special view, not from res.partner
        if not wizard_partner_ids:
            return {}
        data['partner_ids'] = wizard_partner_ids
        datas = {
             'ids': wizard_partner_ids,
             'model': 'account_followup.followup',
             'form': data
        }
        followup_id = datas['form']['followup_id']
        if followup_id:
            record = self.env['account_followup.followup'].browse(followup_id)
        return self.env['report'].get_action(
            record, 'account_followup.report_followup')

    @api.multi
    def do_partner_mail(self):
        # If not defined by latest follow-up level, it will be the default
        #  template if it can find it
        mtp = self.env['mail.template']
        unknown_mails = 0
        for this in self:
            partners_to_email = this.child_ids.filtered(
                lambda child: child.type == 'invoice' and child.email)
            if not partners_to_email and this.email:
                partners_to_email = this
            if partners_to_email:
                level = this.latest_followup_level_id_without_lit
                for partner_to_email in partners_to_email:
                    if level and level.send_email \
                            and level.email_template_id \
                            and level.email_template_id.id:
                        mtp.send_mail(
                            level.email_template_id.id, partner_to_email.id)
                    else:
                        template = self.env.ref(
                            'account_followup'
                            '.email_template_account_followup_default')
                        template.send_mail(partner_to_email.id)
                if this not in partners_to_email:
                    this.message_post(
                        body=_('Overdue email sent to %s' % ', '.join(
                            ['%s <%s>' % (partner.name, partner.email)
                             for partner in partners_to_email])))
            else:
                unknown_mails = unknown_mails + 1
                action_text = _(
                    "Email not sent because of email address "
                    "of partner not filled in")
                if this.payment_next_action_date:
                    payment_action_date = min(
                        fields.Date.context_today(self),
                        partner.payment_next_action_date)
                else:
                    payment_action_date = fields.Date.context_today(self)
                if this.payment_next_action:
                    if action_text not in this.payment_next_action:
                        payment_next_action = this.payment_next_action \
                            + " \n" + action_text
                    else:
                        payment_next_action = this.payment_next_action
                else:
                    payment_next_action = action_text
                this.payment_next_action_date = payment_action_date
                this.payment_next_action = payment_next_action
        return unknown_mails

    def _lines_get_with_partner(self, partner, company_id):
        receivable_id = 1
        moveline_obj = self.env['account.move.line']
        moveline_ids = moveline_obj.search(
            [('partner_id', '=', partner.id),
             ('account_id.user_type_id', '=', receivable_id),
             ('reconciled', '=', False), ('company_id', '=', company_id),
             '|', ('date_maturity', '=', False),
             ('date_maturity', '<=', fields.Date.today())])
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

        return [{
            'line': lines,
            'currency': currency
        } for currency, lines in lines_per_currency.items()]

    def get_followup_table_html(self):
        """ Build the html tables to be included in emails send to partners,
            when reminding them their overdue invoices.
            :param ids: [id] of the partner for whom we are building the tables
            :rtype: string
        """
        partner = self.commercial_partner_id
        followup_table = ''
        if partner.unreconciled_aml_ids:
            company = self.env.user.company_id
            current_date = fields.Date.context_today(self)
            final_res = self._lines_get_with_partner(partner, company.id)

            for currency_dict in final_res:
                currency = currency_dict.get(
                    'line', [{'currency_id': company.currency_id}])[0]['currency_id']
                followup_table += '''
                <table border="2" width=100%%>
                <tr>
                    <td>''' + _("Invoice Date") + '''</td>
                    <td>''' + _("Description") + '''</td>
                    <td>''' + _("Reference") + '''</td>
                    <td>''' + _("Due Date") + '''</td>
                    <td>''' + _("Amount") + " (%s)" % currency.symbol + '''</td>
                    <td>''' + _("Lit.") + '''</td>
                </tr>
                ''' 
                total = 0
                for aml in currency_dict['line']:
                    block = aml['blocked'] and 'X' or ' '
                    total += aml['balance']
                    strbegin = "<TD>"
                    strend = "</TD>"
                    date = aml['date_maturity'] or aml['date']
                    if date <= current_date and aml['balance'] > 0:
                        strbegin = "<TD><B>"
                        strend = "</B></TD>"
                    followup_table += "<TR>" + strbegin + str(aml['date']) + \
                        strend + strbegin + aml['name'] + strend + strbegin + \
                        (aml['ref'] or '') + strend + strbegin + str(date) + \
                        strend + strbegin + str(aml['balance']) + strend + \
                        strbegin + block + strend + "</TR>"

                total = reduce(
                    lambda x, y: x+y['balance'], currency_dict['line'], 0.00)

                total = formatLang(self.env, total, currency_obj=currency)
                followup_table += '''<tr> </tr>
                                </table>
                                <center>''' + _("Amount due") + ''' : %s 
                                    </center>''' % total
        return followup_table

    def write(self, vals):
        if vals.get("payment_responsible_id", False):
            for part in self:
                if part.payment_responsible_id != vals["payment_responsible_id"]:
                    #Find partner_id of user put as responsible
                    responsible_partner_id = self.env["res.users"].browse(
                        vals['payment_responsible_id']).partner_id.id
                    self.env["mail.thread"].message_post(
                        body=_("You became responsible to do the next action "
                        "for the payment follow-up of") + " <b><a href='#id=" +
                        str(part.id) + "&view_type=form&model=res.partner'> " +
                        part.name + " </a></b>", type='comment',
                        subtype="mail.mt_comment", context=self.env.context,
                        model='res.partner', res_id=part.id,
                        partner_ids=[responsible_partner_id])
        return super(ResPartner, self).write(vals)

    def action_done(self):
        for partner in self:
            partner.payment_next_action_date = False
            partner.payment_next_action = ''
            partner.payment_responsible_id = False

    def do_button_print(self):
        company_id = self.env.user.company_id.id
        if not self.env['account.move.line'].search(
            [('partner_id', '=', self.id), ('account_id.user_type_id', '=', 1),
             ('full_reconcile_id', '=', False), ('company_id', '=', company_id),
             '|', ('date_maturity', '=', False),
             ('date_maturity', '<=', fields.Date.today())]
        ):
            raise exceptions.Warning(_(
                "The partner does not have any accounting entries to print "
                "in the overdue report for the current company."))
        self.message_post(body=_('Printed overdue payments report'))
        # build the id of this partner in the psql view. Could be replaced by
        # a search with [('company_id', '=', company_id),
        # ('partner_id', '=', ids[0])]
        wizard_partner_ids = [self.id * 10000 + company_id]
        followup_ids = self.env['account_followup.followup'].search(
            [('company_id', '=', company_id)])
        if not followup_ids:
            raise exceptions.Warning(
                _("There is no followup plan defined for the current company."))
        data = {
            'date': fields.Date.today(),
            'followup_id': followup_ids[0].id,
        }
        # call the print overdue report on this partner
        return self.do_partner_print(wizard_partner_ids, data)

    def _get_amounts_due(self):
        company = self.env.user.company_id
        for partner in self:
            amount_due = 0.0
            for aml in partner.unreconciled_aml_ids:
                if (aml.company_id == company):
                    amount_due += aml.result
            partner.payment_amount_due = amount_due
        return amount_due

    def _get_amounts_overdue(self):
        """
        Function that computes values for the followup functional fields.
        Note that 'payment_amount_due'
        is similar to 'credit' field on res.partner except it filters on user's
         company.
        """
        company = self.env.user.company_id
        current_date = fields.Date.context_today(self)
        for partner in self:
            amount_overdue = 0.0
            for aml in partner.unreconciled_aml_ids:
                if (aml.company_id == company):
                    date_maturity = aml.date_maturity or aml.date
                    if (date_maturity <= current_date):
                        amount_overdue += aml.result
            partner.payment_amount_overdue = amount_overdue
        return amount_overdue

    def _get_earliest_due_date(self):
        """
        Function that computes values for the followup functional fields.
        Note that 'payment_amount_due'
        is similar to 'credit' field on res.partner except it filters on user's
        company.
        """
        company = self.env.user.company_id
        for partner in self:
            worst_due_date = False
            for aml in partner.unreconciled_aml_ids:
                if aml.company_id == company:
                    date_maturity = aml.date_maturity or aml.date
                    if not worst_due_date or date_maturity < worst_due_date:
                        worst_due_date = date_maturity
                partner.payment_earliest_due_date = worst_due_date
        return worst_due_date

    def _get_followup_overdue_query(self, operator, value, overdue_only=False):
        """
        This function is used to build the query and arguments to use when
        making a search on functional fields
            * payment_amount_due
            * payment_amount_overdue
        Basically, the query is exactly the same except that for overdue there
        is an extra clause in the WHERE.

        :param args: arguments given to the search in the usual domain notation
            (list of tuples)
        :param overdue_only: option to add the extra argument to filter on
         overdue accounting entries or not
        :returns: a tuple with
            * the query to execute as first element
            * the arguments for the execution of this query
        :rtype: (string, [])
        """
        company_id = self.env.user.company_id.id
        having_where_clause = ' AND '.join(
            map(lambda x: '(SUM(bal2) %s %%s)' % (operator), operator))
        having_where_clause = str(having_where_clause)
        having_values = [value]
        overdue_only_str = overdue_only and 'AND date_maturity <= NOW()' or ''
        return ('''SELECT pid AS partner_id, SUM(bal2) FROM
                    (SELECT CASE WHEN bal IS NOT NULL THEN bal
                    ELSE 0.0 END AS bal2, p.id as pid FROM
                    (SELECT (debit-credit) AS bal, partner_id
                    FROM account_move_line l
                    WHERE account_id IN
                            (SELECT id FROM account_account
                            WHERE user_type_id=1)
                    ''' + overdue_only_str + '''
                    AND full_reconcile_id IS NULL
                    AND company_id = %s) AS l
                    RIGHT JOIN res_partner p
                    ON p.id = partner_id ) AS pl
                    GROUP BY pid HAVING ''' + having_where_clause, [company_id]
                        + having_values)

    @api.model
    def _payment_overdue_search(self, operator, value):
        if not operator:
            return []
        query, query_args = self._get_followup_overdue_query(
            operator, value, overdue_only=True)
        self.env.cr.execute(query, query_args)
        res = self.env.cr.fetchall()
        if not res:
            return [('id', '=', '0')]
        return [('id', 'in', [x[0] for x in res])]

    @api.model
    def _payment_earliest_date_search(self, operator, value):
        if not operator:
            return []
        company_id = self.env.user.company_id.id
        having_where_clause = ' AND '.join(map(lambda x: '(MIN(l.date_maturity) %s %%s)' % (operator), operator))
        having_values = [value]
        self.env.cr.execute(
            'SELECT partner_id FROM account_move_line l '
            'WHERE account_id IN '
            '(SELECT id FROM account_account '
            'WHERE user_type_id=1) '
            'AND l.company_id = %s '
            'AND full_reconcile_id IS NULL '
            'AND partner_id IS NOT NULL '
            'GROUP BY partner_id HAVING ' + having_where_clause,
            [company_id] + having_values)
        res = self.env.cr.fetchall()
        if not res:
            return [('id', '=', '0')]
        return [('id', 'in', [x[0] for x in res])]

    @api.model
    def _payment_due_search(self, operator, value):
        if not operator:
            return []
        query, query_args = self._get_followup_overdue_query(
            operator, value, overdue_only=False)
        self.env.cr.execute(query, query_args)
        res = self.env.cr.fetchall()
        if not res:
            return [('id', '=', '0')]
        return [('id', 'in', [x[0] for x in res])]

    @api.model
    @api.depends("unreconciled_aml_ids")
    def _get_partners(self):
        partners = set()
        for aml in self:
            if aml.partner_id:
                partners.add(aml.partner_id.id)
        return self

    payment_responsible_id = fields.Many2one(
        'res.users', string='Responsible', help="Optionally you can "
        "assign a user to this field, which will make him responsible for the "
        "action.", copy=False)
    payment_note = fields.Text(
        'Customer Payment Promise', help="Payment Note",
        track_visibility="onchange", copy=False)
    payment_next_action = fields.Text(
        'Next Action', copy=False, help="This is the next action to be taken. "
        "It will automatically be set when the partner gets a follow-up level "
        "that requires a manual action. ")
    payment_next_action_date = fields.Date(
        'Date of next action', copy=False, help="This is when the manual "
        "follow-up is needed. The date will be set to the current date when "
        "the partner gets a follow-up level that requires a manual action. "
        "Can be practical to set manually e.g. to see if he keeps "
        "his promises.")
    unreconciled_aml_ids = fields.One2many(
        'account.move.line', 'partner_id', domain=[
            '&', ('full_reconcile_id', '=', False), '&',
            ('user_type_id', '=', 1)])
    latest_followup_date = fields.Date(
        compute="_get_latest", method=True, string="Latest Follow-up Date",
        help="Latest date that the follow-up level of the partner was changed",
        multi="latest")
    payment_amount_due = fields.Float(
        compute="_get_amounts_due", string="Amount Due", multi="followup",
        search=_payment_due_search)
    payment_amount_overdue = fields.Float(
        compute="_get_amounts_overdue", string="Amount Overdue",
        multi="followup", search=_payment_overdue_search)
    payment_earliest_due_date = fields.Date(
        compute="_get_earliest_due_date", string="Earliest Due Date",
        multi="followup", fnct_search=_payment_earliest_date_search)
    latest_followup_level_id = fields.Many2one(
        'account_followup.followup.line', compute="_get_latest", method=True,
        string="Latest Follow-up Level", help="The maximum follow-up level",
        multi="latest")
    latest_followup_level_id_without_lit = fields.Many2one(
        'account_followup.followup.line', compute="_get_latest", method=True,
        string="Latest Follow-up Level without litigation",
        help="The maximum follow-up level without taking into account the "
        "account move lines with litigation",
        store=False,
        multi="latest")
