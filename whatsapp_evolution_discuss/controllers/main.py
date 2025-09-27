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
        MODIFICADO: Implementa a lógica para postar a mensagem no canal do Discuss,
        processando texto e anexos (mídia) e atribuindo o autor correto.
        """
        if not partner:
            return

        try:
            channel = request.env['discuss.channel'].sudo()._find_or_create_whatsapp_channel(partner, instance)
            
            # --- LÓGICA DE MÍDIA MODIFICADA ---
            message_content = request.context.get('webhook_message_data', {}).get('message', {})
            body, attachment_ids = self._extract_message_content_and_attachments(message_content)
            # --- FIM DA LÓGICA DE MÍDIA ---

            # Lógica de definição de autor permanece a mesma
            is_from_me = message_data.get('key', {}).get('fromMe', False)
            author_id = False

            if is_from_me:
                if instance.user_id and instance.user_id.partner_id:
                    author_id = instance.user_id.partner_id.id
                else:
                    _logger.warning(
                        "Mensagem de saída (webhook) da instância '%s' não pôde ser postada por falta de usuário.",
                        instance.name
                    )
                    return
            else:
                author_id = partner.id
            
            if not author_id:
                _logger.error("Não foi possível determinar um autor válido para a mensagem do webhook.")
                return

            ctx = {'from_webhook': True}

            # Se não houver corpo de texto nem anexos, não há o que postar.
            if not body and not attachment_ids:
                _logger.info("Webhook ignorado para o Discuss: mensagem sem conteúdo de texto ou mídia processável.")
                return 

            # Posta a mensagem com o corpo e os anexos
            channel.with_context(**ctx).message_post(
                body=body,
                author_id=author_id,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
                attachment_ids=attachment_ids
            )
            _logger.info(
                "Mensagem do webhook (com %d anexos) postada no canal #%s com autor ID: %s.",
                len(attachment_ids), channel.id, author_id
            )
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