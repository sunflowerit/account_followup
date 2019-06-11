# -*- coding: utf-8 -*-
# Copyright 2004-2010 Tiny SPRL (<http://tiny.be>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models, api, _


class AccountFollowupLine(models.Model):
    _name = 'account_followup.followup.line'
    _description = 'Follow-up Criteria'
    _order = 'delay'

    def _get_default_template(self):
        try:
            ref = self.env['ir.model.data'].get_object_reference(
                'account_followup', 'email_template_account_followup_default')
            template_id = ref[1]
            obj_name = ref[0]
            obj = self.env[obj_name].browse(template_id)
            return obj
        except ValueError:
            return False

    name = fields.Char('Follow-Up Action', required=True)
    sequence = fields.Integer(
        'Sequence', help="Gives the sequence order when displaying "
        "a list of follow-up lines.")
    delay = fields.Integer(
        'Due Days', help="The number of days after the due date of the "
        "invoice to wait before sending the reminder.  Could be negative "
        "if you want to send a polite alert beforehand.", required=True)
    followup_id = fields.Many2one(
        'account_followup.followup', 'Follow Ups', required=True,
        ondelete="cascade")
    description = fields.Text('Printed Message', translate=True, default="""
        Dear %(partner_name)s,

        Exception made if there was a mistake of ours, it seems that the
        following amount stays unpaid. Please, take appropriate measures in
        order to carry out this payment in the next 8 days.

        Would your payment have been carried out after this mail was sent,
        please ignore this message. Do not hesitate to contact our accounting
        department.

        Best Regards,
        """)
    send_email = fields.Boolean(
        'Send an Email', help="When processing, it will send an email",
        default="True")
    send_letter = fields.Boolean(
        'Send a Letter', help="When processing, it will print a letter",
        default="True")
    manual_action = fields.Boolean(
        'Manual Action', help="When processing, it will set the manual "
        "action to be taken for that customer. ", default="True")
    manual_action_note = fields.Text(
        'Action To Do', placeholder="e.g. Give a phone call, check "
        "with others , ...")
    manual_action_responsible_id = fields.Many2one(
        'res.users', 'Assign a Responsible', ondelete='set null')
    email_template_id = fields.Many2one(
        'mail.template', 'Email Template', ondelete='set null',
        default=_get_default_template)

    _sql_constraints = [('days_uniq', 'unique(followup_id, delay)',
                        'Days of the follow-up levels must be different')]

    @api.constrains('description')
    def _check_description(self):
        for line in self:
            if line.description:
                try:
                    line.description % {'partner_name': '', 'date': '',
                                        'user_signature': '',
                                        'company_name': ''}
                except ValueError:
                    raise Warning(_(
                        'Your description is invalid, use the right legend or '
                        '%% if you want to use the percent character.'))
