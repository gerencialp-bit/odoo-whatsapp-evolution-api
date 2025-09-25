# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import SQL
from datetime import datetime, timedelta
import logging
import re

_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _inherit = 'res.partner'

    # --- Campo movido do whatsapp_evolution_base (Tarefa 1.3) ---
    whatsapp_instance_id = fields.Many2one(
        'whatsapp.instance', string='WhatsApp Instance Origin',
        help='The WhatsApp instance that originated this contact. Used to trace back private contacts.',
        readonly=True,
        copy=False
    )

    # --- Campos de Privacidade (Tarefa 1.2) ---
    is_private = fields.Boolean(
        string="Is Private Contact",
        default=False,
        copy=False,
        index=True,
        help="If checked, this contact is private to the owner and not visible in the main company address book."
    )
    owner_user_id = fields.Many2one(
        'res.users',
        string="Owner",
        help="The user who owns this private contact.",
        readonly=True,
        copy=False,
        index=True
    )
    promoted_date = fields.Datetime(
        string="Promoted On",
        readonly=True,
        copy=False,
        help="Date and time when the contact was promoted to a company contact."
    )

    # ======================= INÍCIO DA ADIÇÃO =======================
    # --- Campos de Verificação do WhatsApp ---
    whatsapp_verified = fields.Boolean(
        string="WhatsApp Verified",
        readonly=True,
        copy=False,
        help="Indicates if the mobile number has been verified as a valid WhatsApp account."
    )
    whatsapp_verified_date = fields.Datetime(
        string="Verification Date",
        readonly=True,
        copy=False,
        help="The last date and time this contact's WhatsApp number was successfully verified."
    )
    can_verify_whatsapp = fields.Boolean(
        string="Can Verify WhatsApp",
        compute='_compute_can_verify_whatsapp',
        help="Technical field to control the visibility of the verification button."
    )
    # ======================== FIM DA ADIÇÃO =========================

    # --- Campos Computados ---
    can_revert_promotion = fields.Boolean(
        string="Can Revert Promotion",
        compute='_compute_can_revert_promotion',
        help="Technical field to check if the current user can revert the promotion within the time window."
    )

    # --- SQL Constraints (Melhor Prática inspirada no muk_contacts) ---
    def init(self):
        """ Garante que um contato da empresa (não privado) não tenha um dono. """
        self.env.cr.execute(
            SQL(
                """
                    CREATE UNIQUE INDEX IF NOT EXISTS res_partner_owner_consistency
                    ON %s (owner_user_id)
                    WHERE is_private IS FALSE
                """,
                SQL.identifier(self._table)
            )
        )

    # --- NOVO CAMPO COMPUTADO PARA O WIDGET DE ÍCONE ---
    contact_type = fields.Selection(
        [('company', 'Company'), ('private', 'Private')],
        string="Contact Type",
        compute='_compute_contact_type',
        store=True # Store para permitir agrupamento e busca se necessário
    )

    # --- Métodos Computados ---
    @api.depends('is_private')
    def _compute_contact_type(self):
        """Define o tipo de contato para uso na UI."""
        for partner in self:
            partner.contact_type = 'private' if partner.is_private else 'company'

    @api.depends('is_private', 'promoted_date', 'owner_user_id')
    def _compute_can_revert_promotion(self):
        """
        Verifica se o usuário atual pode reverter a promoção.
        Isso é verdade se o contato NÃO é privado, o usuário atual é o dono,
        e a data de promoção está dentro da janela de tempo configurada.
        """
        try:
            revert_window_hours = self._get_revert_window_hours()
        except (ValueError, TypeError):
            revert_window_hours = 24  # Fallback
            _logger.warning("Could not parse 'revert_promotion_window_hours'. Using default of 24 hours.")

        for partner in self:
            can_revert = False
            if not partner.is_private and partner.owner_user_id == self.env.user and partner.promoted_date:
                revert_deadline = partner.promoted_date + timedelta(hours=revert_window_hours)
                if datetime.now() <= revert_deadline:
                    can_revert = True
            partner.can_revert_promotion = can_revert

    # ======================= INÍCIO DA ADIÇÃO =======================
    def _compute_can_verify_whatsapp(self):
        """
        Verifica se existe alguma instância disponível para o usuário atual fazer a verificação.
        A busca por instâncias é feita uma única vez para otimizar a performance.
        """
        verifying_instance = self.env['whatsapp.instance']._get_verifying_instance()
        can_verify = bool(verifying_instance)
        for partner in self:
            partner.can_verify_whatsapp = can_verify
    # ======================== FIM DA ADIÇÃO =========================

    # --- Métodos de Ação (Botões) (Tarefa 1.2) ---
    def action_promote_contact(self):
        """Promove um contato particular para um contato da empresa, tornando-o público."""
        self.ensure_one()
        if not self.is_private:
            raise UserError(_("This contact is already a company contact."))
        if self.owner_user_id != self.env.user and not self.env.user.has_group('base.group_system'):
            raise UserError(_("Only the owner or an administrator can promote this contact."))

        self.write({
            'is_private': False,
            'promoted_date': fields.Datetime.now(),
        })
        self.message_post(body=_("Contact promoted to a company contact by %s.") % self.env.user.name)

    def action_revert_contact(self):
        """Permite ao usuário dono reverter sua própria promoção dentro da janela de tempo."""
        self.ensure_one()
        if self.is_private:
            raise UserError(_("This contact is already private."))
        if self.owner_user_id != self.env.user:
            raise UserError(_("Only the original owner can revert this promotion."))

        revert_window_hours = self._get_revert_window_hours()
        revert_deadline = self.promoted_date + timedelta(hours=revert_window_hours)
        if not self.promoted_date or datetime.now() > revert_deadline:
            raise UserError(
                _("The time window (%s hours) to revert this promotion has expired. "
                  "Please contact an administrator.") % revert_window_hours
            )

        self.write({
            'is_private': True,
            'promoted_date': False,
        })
        self.message_post(body=_("Promotion reverted by the owner %s.") % self.env.user.name)

    def action_revert_contact_admin(self):
        """Permite a um administrador reverter a promoção a qualquer momento."""
        self.ensure_one()
        if self.is_private:
            raise UserError(_("This contact is already private."))

        self.write({
            'is_private': True,
            'promoted_date': False,
            # Um admin pode decidir reatribuir o dono, mas por agora, mantemos o original
            # 'owner_user_id': self.env.user.id,
        })
        self.message_post(body=_("Promotion reverted by administrator %s.") % self.env.user.name)

    # ======================= INÍCIO DA ADIÇÃO =======================
    def action_verify_whatsapp(self):
        """
        Ação do botão para verificar o número de celular do contato via API da Evolution.
        """
        if not self:
            return

        instance = self.env['whatsapp.instance']._get_verifying_instance()
        if not instance:
            raise UserError(_("Nenhuma instância conectada do WhatsApp foi encontrada para realizar a verificação. Por favor, contate um administrador."))

        verified_count = 0
        failed_count = 0

        for partner in self:
            if not partner.mobile:
                partner.message_post(body=_("Falha na verificação do WhatsApp: O campo 'Celular' está vazio."))
                failed_count += 1
                continue

            # Limpa o número para enviar para a API (remove tudo que não for dígito)
            clean_number = re.sub(r'\D', '', partner.mobile)
            if not clean_number:
                partner.message_post(body=_("Falha na verificação do WhatsApp: O número de celular '%s' é inválido.") % partner.mobile)
                failed_count += 1
                continue

            try:
                response = self.env['whatsapp.evolution.api']._api_check_whatsapp_numbers(instance, [clean_number])
                
                # A API retorna uma lista, pegamos o primeiro resultado
                if response and isinstance(response, list) and response[0]:
                    result = response[0]
                    if result.get('exists'):
                        partner.write({
                            'whatsapp_verified': True,
                            'whatsapp_verified_date': fields.Datetime.now(),
                        })
                        partner.message_post(body=_("O número de celular (%s) foi verificado com sucesso como uma conta do WhatsApp.") % partner.mobile)
                        verified_count += 1
                    else:
                        partner.write({'whatsapp_verified': False})
                        partner.message_post(body=_("O número de celular (%s) não corresponde a uma conta do WhatsApp.") % partner.mobile)
                        failed_count += 1
                else:
                    raise UserError(_("A API retornou uma resposta inesperada: %s") % response)

            except UserError as e:
                _logger.error("Erro ao verificar o número do WhatsApp para '%s': %s", partner.name, e)
                partner.message_post(body=_("Erro na verificação do WhatsApp: %s") % e)
                failed_count += 1

        # Notificação para o usuário com o resumo
        if verified_count or failed_count:
            message = _("%d contato(s) verificado(s) com sucesso. %d falha(ram).") % (verified_count, failed_count)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Verificação Concluída"),
                    'message': message,
                    'type': 'success' if verified_count and not failed_count else 'warning',
                    'sticky': False,
                }
            }
    # ======================== FIM DA ADIÇÃO =========================
    
    def _get_revert_window_hours(self):
        """Busca o valor do nosso novo modelo de configuração."""
        config = self.env['whatsapp.contact.config'].sudo()._get_config_record()
        return config.revert_promotion_window_hours or 24 # Fallback