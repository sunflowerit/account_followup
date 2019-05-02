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

from odoo import fields, models, api
from odoo.tools.translate import _
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = "res.partner"

    """def fields_view_get(self, view_id=None, view_type=None, toolbar=False, submenu=False):
        res = super(res_partner, self).fields_view_get(view_id=view_id, view_type=view_type,
                                                       toolbar=toolbar, submenu=submenu)
        context = context or {}
        if view_type == 'form' and context.get('Followupfirst'):
            doc = etree.XML(res['arch'], parser=None, base_url=None)
            first_node = doc.xpath("//page[@name='followup_tab']")
            root = first_node[0].getparent()
            root.insert(0, first_node[0])
            res['arch'] = etree.tostring(doc, encoding="utf-8")
        return res"""

    def _get_latest(self):
        res={}
        company = self.env.user.company_id
        for partner in self:
            amls = partner.unreconciled_aml_ids
            latest_date = False
            latest_level = False
            latest_days = False
            latest_level_without_lit = False
            latest_days_without_lit = False
            for aml in amls:
                if (aml.company_id == company) and (aml.followup_line_id != False) and (not latest_days or latest_days < aml.followup_line_id.delay):
                    latest_days = aml.followup_line_id.delay
                    latest_level = aml.followup_line_id.id
                if (aml.company_id == company) and (not latest_date or latest_date < aml.followup_date):
                    latest_date = aml.followup_date
                if (aml.company_id == company) and (aml.blocked == False) and (aml.followup_line_id != False and 
                            (not latest_days_without_lit or latest_days_without_lit < aml.followup_line_id.delay)):
                    latest_days_without_lit =  aml.followup_line_id.delay
                    latest_level_without_lit = aml.followup_line_id.id
            res[partner.id] = {'latest_followup_date': latest_date,
                               'latest_followup_level_id': latest_level,
                               'latest_followup_level_id_without_lit': latest_level_without_lit}
        return res

    @api.cr_uid_ids_context
    def do_partner_manual_action(self, partner_ids): 
        #partner_ids -> res.partner
        for partner in self.browse(partner_ids):
            #Check action: check if the action was not empty, if not add
            action_text= ""
            if partner.payment_next_action:
                action_text = (partner.payment_next_action or '') + "\n" + (partner.latest_followup_level_id_without_lit.manual_action_note or '')
            else:
                action_text = partner.latest_followup_level_id_without_lit.manual_action_note or ''

            #Check date: only change when it did not exist already
            action_date = partner.payment_next_action_date or fields.Date.context_today(self)

            # Check responsible: if partner has not got a responsible already, take from follow-up
            responsible_id = False
            if partner.payment_responsible_id:
                responsible_id = partner.payment_responsible_id.id
            else:
                p = partner.latest_followup_level_id_without_lit.manual_action_responsible_id
                responsible_id = p and p.id or False
            partner.payment_next_action_date = action_date
            partner.payment_next_action = action_text
            partner.payment_responsible_id = responsible_id

    def do_partner_print(self, wizard_partner_ids, data):
        #wizard_partner_ids are ids from special view, not from res.partner
        if not wizard_partner_ids:
            return {}
        data['partner_ids'] = wizard_partner_ids
        datas = {
             'ids': wizard_partner_ids,
             'model': 'account_followup.followup',
             'form': data
        }
        return self.env['report'].get_action(
            [], 'account_followup.report_followup', data=datas)

    @api.cr_uid_ids_context
    def do_partner_mail(self):
        ctx = self.env.context.copy()
        ctx['followup'] = True
        # If not defined by latest follow-up level, it will be the default template if it can find it
        mtp = self.env['mail.template']
        unknown_mails = 0
        for partner in self:
            partners_to_email = [child for child in partner.child_ids if child.type == 'invoice' and child.email]
            if not partners_to_email and partner.email:
                partners_to_email = [partner]
            if partners_to_email:
                level = partner.latest_followup_level_id_without_lit
                for partner_to_email in partners_to_email:
                    if level and level.send_email and level.email_template_id and level.email_template_id.id:
                        mtp.send_mail(level.email_template_id.id, partner_to_email.id)
                    else:
                        mail_template_id = self.env['ir.model.data'].get_object_reference(cr, uid,
                                                        'account_followup', 'email_template_account_followup_default')
                        mtp.send_mail(mail_template_id[1], partner_to_email.id)
                if partner not in partners_to_email:
                    self.message_post([partner.id], body=_('Overdue email sent to %s' % ', '.join(['%s <%s>' % (partner.name, partner.email) for partner in partners_to_email])))
            else:
                unknown_mails = unknown_mails + 1
                action_text = _("Email not sent because of email address of partner not filled in")
                if partner.payment_next_action_date:
                    payment_action_date = min(fields.Date.context_today(self), partner.payment_next_action_date)
                else:
                    payment_action_date = fields.Date.context_today(self)
                if partner.payment_next_action:
                    if action_text not in partner.payment_next_action:
                        payment_next_action = partner.payment_next_action + " \n" + action_text
                    else:
                        payment_next_action = partner.payment_next_action
                else:
                    payment_next_action = action_text
                partner.payment_next_action_date = payment_action_date
                partner.payment_next_action = payment_next_action
        return unknown_mails

    def get_followup_table_html(self):
        """ Build the html tables to be included in emails send to partners,
            when reminding them their overdue invoices.
            :param ids: [id] of the partner for whom we are building the tables
            :rtype: string
        """
        from report import account_followup_print

        assert len(ids) == 1
        partner = self.browse(ids[0]).commercial_partner_id
        #copy the context to not change global context. Overwrite it because _() looks for the lang in local variable 'context'.
        #Set the language to use = the partner language
        context = dict(self.env.context, lang=partner.lang)
        followup_table = ''
        if partner.unreconciled_aml_ids:
            company = self.env['res.users'].browse(uid).company_id
            current_date = fields.Date.context_today(self)
            rml_parse = account_followup_print.report_rappel("followup_rml_parser")
            final_res = rml_parse._lines_get_with_partner(partner, company.id)

            for currency_dict in final_res:
                currency = currency_dict.get('line', [{'currency_id': company.currency_id}])[0]['currency_id']
                followup_table += '''
                <table border="2" width=100%%>
                <tr>
                    <td>''' + _("Invoice Date") + '''</td>
                    <td>''' + _("Description") + '''</td>
                    <td>''' + _("Reference") + '''</td>
                    <td>''' + _("Due Date") + '''</td>
                    <td>''' + _("Amount") + " (%s)" % (currency.symbol) + '''</td>
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
                    followup_table +="<TR>" + strbegin + str(aml['date']) + strend + strbegin + aml['name'] + strend + strbegin + (aml['ref'] or '') + strend + strbegin + str(date) + strend + strbegin + str(aml['balance']) + strend + strbegin + block + strend + "</TR>"

                total = reduce(lambda x, y: x+y['balance'], currency_dict['line'], 0.00)

                total = rml_parse.formatLang(total, dp='Account', currency_obj=currency)
                followup_table += '''<tr> </tr>
                                </table>
                                <center>''' + _("Amount due") + ''' : %s </center>''' % (total)
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
        #search if the partner has accounting entries to print. If not, it may not be present in the
        #psql view the report is based on, so we need to stop the user here.
        if not self.env['account.move.line'].search(
            [('partner_id', '=', self.id), ('account_id.user_type_id', '=', 1),
             ('full_reconcile_id', '=', False), ('company_id', '=', company_id),
             '|', ('date_maturity', '=', False),
             ('date_maturity', '<=', fields.Date.today())]
        ):
            raise UserError(_('Error!'),_("The partner does not have any accounting entries to print in the overdue report for the current company."))
        self.message_post(body=_('Printed overdue payments report'))
        #build the id of this partner in the psql view. Could be replaced by a search with [('company_id', '=', company_id),('partner_id', '=', ids[0])]
        wizard_partner_ids = [self.id * 10000 + company_id]
        followup_ids = self.env['account_followup.followup'].search([('company_id', '=', company_id)])
        if not followup_ids:
            raise UserError(
                _('Error!'),
                _("There is no followup plan defined for the current company."))
        data = {
            'date': fields.Date.today(),
            'followup_id': followup_ids[0].id,
        }
        #call the print overdue report on this partner
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
                if (aml.company_id == company):
                    date_maturity = aml.date_maturity or aml.date
                    if not worst_due_date or date_maturity < worst_due_date:
                        worst_due_date = date_maturity
                partner.payment_earliest_due_date = worst_due_date
        return worst_due_date

    def _get_followup_overdue_query(self, args, overdue_only=False):
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
            map(lambda x: '(SUM(bal2) %s %%s)' % (x[1]), args))
        having_values = [x[2] for x in args]
        query = self.env['account.move.line']._query_get(
            context=self.env.context)
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
                    AND company_id = %s
                    AND ''' + query + ''') AS l
                    RIGHT JOIN res_partner p
                    ON p.id = partner_id ) AS pl
                    GROUP BY pid HAVING ''' + having_where_clause, [company_id]
                        + having_values)

    def _payment_overdue_search(self, obj, name, args):
        if not args:
            return []
        query, query_args = self._get_followup_overdue_query(args, overdue_only=True)
        self.env.cr.execute(query, query_args)
        res = self.env.cr.fetchall()
        if not res:
            return [('id','=','0')]
        return [('id','in', [x[0] for x in res])]

    def _payment_earliest_date_search(self, obj, name, args):
        if not args:
            return []
        #company_id = self.env['res.users'].browse(uid).company_id.id
        company_id = self.env.user.company_id.id
        having_where_clause = ' AND '.join(map(lambda x: '(MIN(l.date_maturity) %s %%s)' % (x[1]), args))
        having_values = [x[2] for x in args]
        query = self.env['account.move.line']._query_get(context=self.env.context)
        self.env.cr.execute('SELECT partner_id FROM account_move_line l '\
                    'WHERE account_id IN '\
                        '(SELECT id FROM account_account '\
                        'WHERE user_type_id=1) '\
                    'AND l.company_id = %s '
                    'AND full_reconcile_id IS NULL '\
                    'AND '+query+' '\
                    'AND partner_id IS NOT NULL '\
                    'GROUP BY partner_id HAVING '+ having_where_clause,
                     [company_id] + having_values)
        res = self.env.cr.fetchall()
        if not res:
            return [('id','=','0')]
        return [('id','in', [x[0] for x in res])]

    def _payment_due_search(self, obj, name, args):
        if not args:
            return []
        query, query_args = self._get_followup_overdue_query(args, overdue_only=False)
        self.env.cr.execute(query, query_args)
        res = self.env.cr.fetchall()
        if not res:
            return [('id','=','0')]
        return [('id','in', [x[0] for x in res])]

    @api.model
    @api.depends("unreconciled_aml_ids")
    def _get_partners(self, ids):
        #this function search for the partners linked to all account.move.line 'ids' that have been changed
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
        fnct_search=_payment_due_search)
    payment_amount_overdue = fields.Float(
        compute="_get_amounts_overdue", string="Amount Overdue",
        multi="followup", fnct_search=_payment_overdue_search)
    payment_earliest_due_date = fields.Date(
        compute="_get_earliest_due_date", string="Earliest Due Date",
        multi="followup", fnct_search=_payment_earliest_date_search)
    latest_followup_level_id = fields.Many2one('account_followup.followup.line', compute="_get_latest", method=True,
            string="Latest Follow-up Level",
            help="The maximum follow-up level", 
            store= False,
            #store={
                #'res.partner': (lambda self, cr, uid, ids, c: ids,[],10),
                #'account.move.line': (lambda self, cr, uid, ids, c: ids, ['followup_line_id'], 10),
                #'account.move.line': (_get_partners, ['followup_line_id'], 10),
            #}, 
            multi="latest")
    latest_followup_level_id_without_lit = fields.Many2one('account_followup.followup.line', compute="_get_latest", method=True, 
            string="Latest Follow-up Level without litigation", 
            help="The maximum follow-up level without taking into account the account move lines with litigation", 
            store=False,
            #store={
                #'res.partner': (lambda self, cr, uid, ids, c: ids,[],10),
                #'account.move.line': (lambda self, cr, uid, ids, c: ids, ['followup_line_id'], 10),
                #'account.move.line': (_get_partners, ['followup_line_id'], 10),
            #}, 
            multi="latest")

