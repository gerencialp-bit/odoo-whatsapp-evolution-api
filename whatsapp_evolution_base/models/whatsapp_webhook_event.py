# -*- coding: utf-8 -*-
from odoo import fields, models

class WhatsappWebhookEvent(models.Model):
    _name = 'whatsapp.webhook.event'
    _description = 'WhatsApp Webhook Event'
    _order = 'name'

    name = fields.Char(string="Event Name", required=True, readonly=True)

    _sql_constraints = [
        ('name_uniq', 'unique (name)', "Event Name must be unique!"),
    ]