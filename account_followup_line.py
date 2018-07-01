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

from odoo import api
from odoo import fields, models
from lxml import etree
from odoo.tools.translate import _

class followup_line(models.Model):

    def _get_default_template(self):
        try:
            ref = self.env['ir.model.data'].get_object_reference('account_followup', 'email_template_account_followup_default')
            template_id = ref[1]
            obj_name = ref[0]
            obj = self.env[obj_name].browse(template_id)
            return obj
        except ValueError:
            return False

    _name = 'account_followup.followup.line'
    _description = 'Follow-up Criteria'

    name = fields.Char('Follow-Up Action', required=True)
    sequence = fields.Integer('Sequence', help="Gives the sequence order when displaying a list of follow-up lines.")
    delay = fields.Integer('Due Days', help="The number of days after the due date of the invoice to wait before sending the reminder.  Could be negative if you want to send a polite alert beforehand.", required=True)
    followup_id = fields.Many2one('account_followup.followup', 'Follow Ups', required=True, ondelete="cascade")
    description = fields.Text('Printed Message', translate=True, default="""
        Dear %(partner_name)s,

        Exception made if there was a mistake of ours, it seems that the following amount stays unpaid. Please, take appropriate measures in order to carry out this payment in the next 8 days.

        Would your payment have been carried out after this mail was sent, please ignore this message. Do not hesitate to contact our accounting department.

        Best Regards,
        """)
    send_email = fields.Boolean('Send an Email', help="When processing, it will send an email", default="True")
    send_letter = fields.Boolean('Send a Letter', help="When processing, it will print a letter", default="True")
    manual_action = fields.Boolean('Manual Action', help="When processing, it will set the manual action to be taken for that customer. ", default="True")
    manual_action_note = fields.Text('Action To Do', placeholder="e.g. Give a phone call, check with others , ...")
    manual_action_responsible_id = fields.Many2one('res.users', 'Assign a Responsible', ondelete='set null')
    email_template_id = fields.Many2one('mail.template', 'Email Template', ondelete='set null', default=_get_default_template)

    _order = 'delay'
    _sql_constraints = [('days_uniq', 'unique(followup_id, delay)', 'Days of the follow-up levels must be different')]

    def _check_description(self):
        lang = self.env.user.lang
        for line in self:
            print(line)
            if line.description:
                try:
                    line.description % {'partner_name': '', 'date':'', 'user_signature': '', 'company_name': ''}
                except:
                    return False
        return True

    _constraints = [
        (_check_description, 'Your description is invalid, use the right legend or %% if you want to use the percent character.', ['description']),
    ]