# models/whatsapp_message.py 
# -*- coding: utf-8 -*- 
from odoo import fields, models, api 
from markupsafe import Markup 
import json 

class WhatsappMessage(models.Model): 
    _name = 'whatsapp.message' 
    _description = 'WhatsApp Message' 
    _order = 'timestamp desc' 
    partner_id = fields.Many2one( 
        'res.partner', 
        string='Contato', 
        ondelete='set null',# tracking=True, 
    )
    instance_id = fields.Many2one('whatsapp.instance', string='WhatsApp Instance', required=True, ondelete='cascade') 
    message_id = fields.Char(string='Message ID', required=True, index=True, copy=False) 
    timestamp = fields.Datetime(string='Timestamp', required=True) 
    message_direction = fields.Selection([('inbound', 'Inbound'), ('outbound', 'Outbound')], string='Direction', required=True) 
    sender_name = fields.Char(string='Sender Name', readonly=True, help="Nome de quem enviou, conforme reportado pela API.") 
    is_group = fields.Boolean(string='Group Message', readonly=True) 
    phone_number = fields.Char(string='Phone Number', readonly=True) 
    message_type = fields.Char(string='Message Type') 
    body = fields.Text(string='Message Body / Caption') 
    media_type = fields.Selection([ 
        ('image', 'Image'), ('video', 'Video'), ('sticker', 'Sticker'), 
        ('audio', 'Audio'), ('document', 'Document'), ('other', 'Other'), 
    ], string='Media Type', readonly=True) 
    media_url = fields.Char(string="Media URL", readonly=True) 
    media_filename = fields.Char(string="Media Filename", readonly=True) 
    media_preview = fields.Html(string="Media Preview", compute='_compute_media_preview', sanitize=False) 
    reacted_message_id = fields.Many2one('whatsapp.message', string="Reacted Message", readonly=True) 
    state = fields.Selection([('sent', 'Sent'), ('delivered', 'Delivered'), ('read', 'Read'), ('failed', 'Failed')], string='Status', default='sent') 
    failure_reason = fields.Text(string='Failure Reason') 
    raw_json = fields.Text(string='Raw JSON', readonly=True) 
    _sql_constraints = [('message_id_unique', 'UNIQUE(message_id, instance_id)', 'Message ID must be unique per instance!')] 

    @api.depends('media_type', 'media_url', 'media_filename', 'body', 'raw_json') 
    def _compute_media_preview(self): 
        for message in self: 
            preview_html = '' 
            if message.media_url: 
                media_player_html = '' 
                download_url = f'/whatsapp/media/download/{message.id}' 
                
                if message.media_type in ['image', 'sticker']: 
                    media_player_html = f'<img src="{message.media_url}" class="img img-fluid border rounded" style="max-height: 450px;" alt="Preview da Mídia"/>' 
                elif message.media_type == 'audio': 
                    media_player_html = f'<audio src="{message.media_url}" controls="controls" preload="none" class="w-100">Áudio não suportado.</audio>' 
                elif message.media_type == 'video': 
                    media_player_html = f'<video src="{message.media_url}" controls="controls" preload="metadata" class="img img-fluid border rounded" style="max-height: 450px;">Vídeo não suportado.</video>' 
                elif message.media_type == 'document': 
                    thumbnail_b64 = '' 
                    try: 
                        raw_data = json.loads(message.raw_json or '{}') 
                        thumbnail_b64 = raw_data.get('data', {}).get('message', {}).get('documentMessage', {}).get('jpegThumbnail') 
                    except Exception: 
                        thumbnail_b64 = '' # Ignora erros de parsing 
                    
                    if thumbnail_b64: 
                        media_player_html = f'<img src="data:image/jpeg;base64,{thumbnail_b64}" class="img img-fluid border rounded" style="max-height: 450px;" alt="Miniatura do Documento"/>' 
                    else: 
                        media_player_html = '<div class="text-center p-5 bg-light border rounded"><i class="fa fa-file-text-o fa-5x text-muted"/></div>' 

                # --- UI REFINADA PARA FORM VIEW --- 
                preview_html = f''' 
                    <div class="o_whatsapp_media_container mb-2">{media_player_html}</div> 
                    <div class="o_whatsapp_attachment_details mt-2 p-2 border rounded bg-light"> 
                        <p class="mb-1"><strong>Anexo:</strong> <span class="text-muted">{message.media_filename or 'N/A'}</span></p> 
                        <div> 
                            <a href="{message.media_url}" target="_blank" class="btn btn-sm btn-secondary me-2" title="Abrir em nova aba"><i class="fa fa-external-link"/> Abrir Original</a> 
                            <a href="{download_url}" class="btn btn-sm btn-primary" title="Baixar arquivo"><i class="fa fa-download"/> Baixar</a> 
                        </div> 
                    </div> 
                ''' 
            
            message.media_preview = Markup(preview_html)