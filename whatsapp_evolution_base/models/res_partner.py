from odoo import fields, models

class ResPartner(models.Model):
    _inherit = 'res.partner'

    whatsapp_instance_id = fields.Many2one(
        'whatsapp.instance',
        string='WhatsApp Instance',
        help='WhatsApp instance associated with this partner.'
    )