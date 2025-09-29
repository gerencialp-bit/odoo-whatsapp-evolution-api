# -*- coding: utf-8 -*-
import logging
import base64
# ======================= IMPORTAÇÕES ADICIONADAS ======================= 
import urllib.request 
import urllib.parse 
import os 
import mimetypes # <- Importa o módulo padrão do Python, não o do Odoo 
# ====================================================================== 
from odoo import http, _ 
from odoo.http import request 
from odoo.addons.whatsapp_contact_management.controllers.main import ContactWebhookController 

_logger = logging.getLogger(__name__) 

class DiscussWebhookController(ContactWebhookController):

    def _post_message_in_discuss_channel(self, instance, message_data, partner):
        """
        CORRIGIDO: Separa a criação da mensagem da atualização com campos customizados.
        """
        if not partner:
            return

        try:
            channel = request.env['discuss.channel'].sudo()._find_or_create_whatsapp_channel(partner, instance)
            message_content = request.context.get('webhook_message_data', {}).get('message', {})
            is_from_me = message_data.get('key', {}).get('fromMe', False)
            message_id_str = message_data.get('key', {}).get('id')
            
            if 'reactionMessage' in message_content:
                reaction = message_content['reactionMessage']
                original_msg_id = reaction.get('key', {}).get('id')
                emoji = reaction.get('text', '')
                 
                original_message = request.env['mail.message'].sudo().search([
                    ('whatsapp_message_id_str', '=', original_msg_id)
                ], limit=1)

                if original_message:
                    author_partner = partner if not is_from_me else (instance.user_id.partner_id if instance.user_id else request.env['res.partner'])
                     
                    # ======================= INÍCIO DA CORREÇÃO =======================
                    # Busca a reação existente
                    existing_reaction = request.env['mail.message.reaction'].sudo().search([
                        ('message_id', '=', original_message.id),
                        ('partner_id', '=', author_partner.id),
                    ])
                     
                    # Se a reação recebida for vazia, significa remoção
                    if not emoji and existing_reaction:
                        existing_reaction.sudo().unlink()
                        _logger.info("Reação do parceiro #%s removida da mensagem #%s.", author_partner.id, original_message.id)
                    # Se não for vazia, cria ou atualiza
                    elif emoji:
                        if existing_reaction and existing_reaction.content != emoji:
                            # Se o emoji mudou, remove o antigo
                            existing_reaction.sudo().unlink()
                         
                        # Cria o novo (só se não existir um igual)
                        if not self.env['mail.message.reaction'].sudo().search_count([
                            ('message_id', '=', original_message.id),
                            ('partner_id', '=', author_partner.id),
                            ('content', '=', emoji)
                        ]):
                            self.env['mail.message.reaction'].sudo().create({
                                'message_id': original_message.id,
                                'partner_id': author_partner.id,
                                'content': emoji,
                            })
                            _logger.info("Reação '%s' do parceiro #%s adicionada/atualizada na mensagem #%s.", emoji, author_partner.id, original_message.id)
                    # ======================== FIM DA CORREÇÃO =========================
                    # ======================= INÍCIO DA CORREÇÃO ======================= 
                    # Notifica o Odoo de que a mensagem original foi alterada. 
                    # Isso força o frontend a buscar os dados atualizados, incluindo as novas reações. 
                    original_message.message_format() 
                    # ======================== FIM DA CORREÇÃO ========================= 
                return
            
            body, attachment_ids = self._extract_message_content_and_attachments(message_content)
            
            author_id = False
            if is_from_me:
                author_id = instance.user_id.partner_id.id if instance.user_id and instance.user_id.partner_id else False
            else:
                author_id = partner.id
            
            if not author_id:
                _logger.error("Não foi possível determinar um autor válido para a mensagem do webhook.")
                return

            if not body and not attachment_ids:
                _logger.info("Webhook ignorado para o Discuss: mensagem sem conteúdo processável.")
                return

            # ======================= INÍCIO DA CORREÇÃO DE RESPOSTA =======================
            post_vals = {
                'body': body,
                'author_id': author_id,
                'message_type': 'comment',
                'subtype_xmlid': 'mail.mt_comment',
                'attachment_ids': attachment_ids,
            }
            
            # Lógica de busca de contexto mais robusta
            context_info = message_content.get('contextInfo') or \
                           message_data.get('contextInfo') or \
                           message_content.get('extendedTextMessage', {}).get('contextInfo')

            if context_info:
                quoted_msg_id = context_info.get('stanzaId')
                if quoted_msg_id:
                    # Busca a mensagem original no Discuss usando nosso campo de rastreamento
                    parent_message = request.env['mail.message'].sudo().search([
                        ('whatsapp_message_id_str', '=', quoted_msg_id)
                    ], limit=1)
                    if parent_message:
                        post_vals['parent_id'] = parent_message.id
            
            ctx = {'from_webhook': True}
            
            new_message = channel.with_context(**ctx).message_post(**post_vals)
            
            if new_message and message_id_str:
                new_message.sudo().write({
                    'whatsapp_message_id_str': message_id_str
                })
            
            _logger.info("Mensagem do webhook (ID: %s) postada no canal #%s e atualizada.", message_id_str, channel.id)
            # ======================== FIM DA CORREÇÃO DE RESPOSTA =========================

        except Exception as e:
            _logger.error("Falha ao postar mensagem do webhook no canal do Discuss: %s", e, exc_info=True)

    def _extract_message_content_and_attachments(self, message_content):
        """
        CORRIGIDO: Extrai o corpo do texto e cria anexos a partir do 'base64' OU baixando de uma 'mediaUrl'.
        """
        body = ""
        attachment_ids = []
        
        media_types = [
            'imageMessage', 'videoMessage', 'stickerMessage',
            'audioMessage', 'documentMessage'
        ]

        if 'conversation' in message_content:
            body = message_content['conversation']
        elif 'extendedTextMessage' in message_content:
            body = message_content.get('extendedTextMessage', {}).get('text', '')
        
        for media_type in media_types:
            if media_type in message_content:
                media_data = message_content[media_type]
                binary_content = None

                # --- INÍCIO DA NOVA LÓGICA DE DOWNLOAD ---
                # Prioridade 1: Tenta obter o conteúdo de 'base64'
                base64_content_str = message_content.get('base64')
                if base64_content_str:
                    try:
                        binary_content = base64.b64decode(base64_content_str)
                    except Exception:
                        _logger.warning("Não foi possível decodificar o conteúdo base64 do webhook.")
                
                # Prioridade 2: Se não houver 'base64', tenta baixar da 'mediaUrl'
                elif not binary_content and message_content.get('mediaUrl'):
                    media_url = message_content['mediaUrl']
                    _logger.info(f"Tentando baixar mídia da URL: {media_url}")
                    try:
                        # Usando urllib.request conforme sugerido, com timeout
                        with urllib.request.urlopen(media_url, timeout=20) as response:
                            binary_content = response.read()
                    except Exception as e:
                        _logger.error(f"Falha ao baixar mídia da URL {media_url}: {e}")
                        continue # Pula para o próximo tipo de mídia se o download falhar
                
                if not binary_content:
                    _logger.warning("Não foi encontrado conteúdo de mídia (nem base64, nem URL válida) para o tipo: %s", media_type)
                    continue
                # --- FIM DA NOVA LÓGICA DE DOWNLOAD ---

                caption = media_data.get('caption', '')
                if caption and not body:
                    body = caption
                
                # Tenta obter um nome de arquivo, com fallbacks
                filename = media_data.get('fileName') or media_data.get('title')
                if not filename:
                    mimetype = media_data.get('mimetype', '')
                    ext = mimetypes.guess_extension(mimetype.split(';')[0]) if mimetype else ''
                    filename = f"whatsapp_media{ext or '.bin'}"
                
                try:
                    # 'datas' no Odoo espera uma string codificada em base64
                    attachment = request.env['ir.attachment'].sudo().create({
                        'name': filename,
                        'datas': base64.b64encode(binary_content),
                        'res_model': 'mail.compose.message',
                        'res_id': 0
                    })
                    attachment_ids.append(attachment.id)

                    # ======================= INÍCIO DA CORREÇÃO =======================
                    # Se o anexo for um áudio, cria o metadado para o player do Discuss.
                    if media_type == 'audioMessage':
                        request.env['discuss.voice.metadata'].sudo().create({
                            'attachment_id': attachment.id
                        })
                        _logger.info("Metadado de voz criado para o anexo de áudio #%s", attachment.id)
                    # ======================== FIM DA CORREÇÃO =========================

                except Exception as e:
                    _logger.error("Falha ao criar anexo a partir de dados binários do webhook: %s", e)
        
        return body, attachment_ids