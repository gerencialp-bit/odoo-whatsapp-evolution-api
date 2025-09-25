# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import UserError

class WhatsappContactConfig(models.Model):
    _name = 'whatsapp.contact.config'
    _description = 'WhatsApp Contact Management Configuration (Singleton)'

    name = fields.Char(default='WhatsApp Contact Configuration', readonly=True, required=True)
    revert_promotion_window_hours = fields.Integer(
        string="Revert Promotion Window (Hours)",
        default=24,
        help="Period (in hours) during which a user can revert the promotion of their own contact."
    )

    @api.model
    def create(self, vals):
        if self.search_count([]) > 0:
            raise UserError(_('There can be only one WhatsApp Contact Configuration record.'))
        return super(WhatsappContactConfig, self).create(vals)

    def unlink(self):
        raise UserError(_('You cannot delete the WhatsApp Contact Configuration record.'))

    @api.model
    def _get_config_record(self):
        """ Helper method to get the singleton record. """
        return self.env.ref('whatsapp_contact_management.whatsapp_contact_config_singleton_record')