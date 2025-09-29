# -*- coding: utf-8 -*-

import json
import requests
import logging

from odoo import models, fields, api, _ as odoo_t
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class EvolutionApi(models.AbstractModel):
    _name = 'whatsapp.evolution.api'
    _description = 'Evolution API Abstraction Layer'

    @api.model
    def _send_api_request(self, instance_id, method, endpoint, payload=None):
        base_url, _ = instance_id._get_api_config()
        if not instance_id.api_key:
            raise UserError(odoo_t("A Chave da API (Token) não está configurada para a instância %s.") % instance_id.name)

        # --- CORREÇÃO DA URL APLICADA AQUI ---
        clean_base_url = base_url.rstrip('/')
        clean_endpoint = endpoint if endpoint.startswith('/') else f'/{endpoint}'
        url = f"{clean_base_url}{clean_endpoint}"
        # --- FIM DA CORREÇÃO ---
         
        headers = { 'Content-Type': 'application/json', 'apikey': instance_id.api_key }

        try:
            response = requests.request(method.upper(), url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.RequestException as e:
            _logger.error("Erro ao enviar requisição para a API da Evolution: %s", e)
            raise UserError(odoo_t("Erro ao comunicar com a API da Evolution: %s") % str(e))

    @api.model
    def _send_api_request_global(self, base_url, api_key, method, endpoint, payload=None):
        headers = {'Content-Type': 'application/json', 'apikey': api_key}
        
        # Garante que a base_url não tenha uma barra no final e que o endpoint comece com uma.
        # Isso evita o problema de barras duplas (//).
        clean_base_url = base_url.rstrip('/')
        clean_endpoint = endpoint if endpoint.startswith('/') else f'/{endpoint}'
        url = f"{clean_base_url}{clean_endpoint}"

        try:
            response = requests.request(method.upper(), url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            # Adicionar log da resposta para facilitar o debug futuro
            _logger.info("API Response from %s: %s", url, response.text)
            return response.json() if response.content else {}
        except requests.exceptions.HTTPError as e:
            # Tenta extrair uma mensagem de erro mais detalhada do corpo da resposta da API
            error_details = e.response.text
            _logger.error("Erro HTTP ao enviar requisição global para a API da Evolution (%s): %s", url, error_details)
            raise UserError(odoo_t("Erro ao comunicar com a API da Evolution: %s - %s") % (str(e), error_details))
        except requests.exceptions.RequestException as e:
            _logger.error("Erro de conexão ao enviar requisição global para a API da Evolution (%s): %s", e)
            raise UserError(odoo_t("Erro de conexão ao comunicar com a API da Evolution: %s") % str(e))
             
    @api.model
    def _api_get_instance_connect(self, instance_id):
        endpoint = f"/instance/connect/{instance_id.name}"
        return self._send_api_request(instance_id, 'GET', endpoint)

    @api.model
    def _api_logout_instance(self, instance_id):
        endpoint = f"/instance/logout/{instance_id.name}"
        return self._send_api_request(instance_id, 'DELETE', endpoint)

    @api.model
    def _api_restart_instance(self, instance_id):
        endpoint = f"/instance/restart/{instance_id.name}"
        return self._send_api_request(instance_id, 'PUT', endpoint)

    @api.model
    def _api_delete_instance(self, instance_id):
        base_url, api_key = instance_id._get_api_config()
        endpoint = f"/instance/delete/{instance_id.name}"
        return self._send_api_request_global(base_url, api_key, 'DELETE', endpoint)

    @api.model
    def _api_set_webhook(self, instance_id, webhook_payload):
        """Configura o webhook para uma instância específica."""
        endpoint = f"/webhook/set/{instance_id.name}"
        # A configuração do webhook usa a chave da PRÓPRIA instância, não a global.
        return self._send_api_request(instance_id, 'POST', endpoint, payload=webhook_payload)

    # ============================ INÍCIO DA NOVA FUNÇÃO ============================
    @api.model
    def _api_set_settings(self, instance_id, settings_payload):
        """
        Define as configurações para uma instância específica.
        """
        endpoint = f"/settings/set/{instance_id.name}"
        return self._send_api_request(instance_id, 'POST', endpoint, payload=settings_payload)
     # ============================= FIM DA NOVA FUNÇÃO ==============================

    @api.model
    def _api_find_webhook(self, instance_id):
        """Busca a configuração de webhook existente para uma instância."""
        endpoint = f"/webhook/find/{instance_id.name}"
        return self._send_api_request(instance_id, 'GET', endpoint)

    @api.model
    def _api_fetch_profile_picture_url(self, instance_id, phone_number):
        """
        Busca a URL da foto de perfil para um determinado número de telefone.
        """
        endpoint = f"/chat/fetchProfilePictureUrl/{instance_id.name}"
        payload = {'number': phone_number}
        # Este endpoint específico usa POST, conforme a documentação
        return self._send_api_request(instance_id, 'POST', endpoint, payload=payload)

    # ======================= INÍCIO DA ADIÇÃO =======================
    @api.model
    def _api_check_whatsapp_numbers(self, instance_id, numbers):
        """
        Verifica se uma lista de números de telefone possui contas do WhatsApp.
        """
        endpoint = f"/chat/whatsappNumbers/{instance_id.name}"
        # A API espera uma lista de strings. Garante que `numbers` seja sempre uma lista.
        payload = {'numbers': numbers if isinstance(numbers, list) else [numbers]}
        return self._send_api_request(instance_id, 'POST', endpoint, payload=payload)
    # ======================== FIM DA ADIÇÃO =========================

    # ======================= INÍCIO DAS NOVAS FUNÇÕES DE ENVIO =======================
    @api.model
    def _api_send_text(self, instance_id, number, text, quoted_message=None):
        """
        Envia uma mensagem de texto simples, com a estrutura de payload corrigida.
        """
        endpoint = f"/message/sendText/{instance_id.name}"
        
        # ======================= CORREÇÃO NO PAYLOAD =======================
        # Revertendo para a estrutura "plana" que a sua API espera.
        payload = {
            "number": str(number),
            "text": text,
        }
        
        if quoted_message:
            payload['quoted'] = quoted_message
        # ===============================================================

        _logger.info("Enviando payload para /message/sendText: %s", json.dumps(payload, indent=2))
        
        return self._send_api_request(instance_id, 'POST', endpoint, payload=payload)

    # ======================= INÍCIO DAS ALTERAÇÕES =======================
    @api.model
    def _api_send_media(self, instance_id, number, mediatype, media_url_or_base64, caption='', file_name=''):
        """
        MODIFICADO: Agora envia apenas imagem, vídeo ou documento.
        """
        endpoint = f"/message/sendMedia/{instance_id.name}"
        payload = {
            "number": number,
            "mediatype": mediatype, # 'image', 'video', ou 'document'
            "media": media_url_or_base64,
            "caption": caption,
            "fileName": file_name,
        }
        return self._send_api_request(instance_id, 'POST', endpoint, payload=payload)

    @api.model
    def _api_send_audio(self, instance_id, number, audio_url_or_base64):
        """
        NOVO: Envia uma mensagem de áudio (PTT), conforme a documentação da API.
        """
        endpoint = f"/message/sendWhatsAppAudio/{instance_id.name}"
        payload = {
            "number": number,
            "audio": audio_url_or_base64, # A chave correta é 'audio'
        }
        return self._send_api_request(instance_id, 'POST', endpoint, payload=payload)

    @api.model
    def _api_send_sticker(self, instance_id, number, sticker_url_or_base64):
        """
        NOVO: Envia uma figurinha (sticker), conforme a documentação da API.
        """
        endpoint = f"/message/sendSticker/{instance_id.name}"
        payload = {
            "number": number,
            "sticker": sticker_url_or_base64, # A chave correta é 'sticker'
        }
        return self._send_api_request(instance_id, 'POST', endpoint, payload=payload)

    @api.model
    def _api_send_reaction(self, instance_id, reaction_payload):
        """
        NOVO: Envia uma reação a uma mensagem existente.
        A documentação não mostra 'number' no payload principal,
        apenas dentro da chave 'key'.
        """
        endpoint = f"/message/sendReaction/{instance_id.name}"
        
        # Log do payload exato que estamos enviando para a API.
        _logger.info("Enviando payload para /message/sendReaction: %s", json.dumps(reaction_payload, indent=2))
        
        # O payload já deve vir totalmente formatado.
        return self._send_api_request(instance_id, 'POST', endpoint, payload=reaction_payload)
    # ======================== FIM DAS ALTERAÇÕES =========================