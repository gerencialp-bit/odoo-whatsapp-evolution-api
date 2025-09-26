/** @odoo-module **/

import { Thread } from "@mail/core/common/thread_model";
import { patch } from "@web/core/utils/patch";

patch(Thread.prototype, {
    /**
     * Computes the Discuss App category for the thread.
     * Assigns 'whatsapp' channels to the 'whatsapp' category.
     */
    _computeDiscussAppCategory() {
        if (this.channel_type === "whatsapp") {
            return this.store.discuss.whatsapp;
        }
        return super._computeDiscussAppCategory(...arguments);
    },

    // ============================ INÍCIO DA NOVA ADIÇÃO ============================
    /**
     * Um usuário não deve poder "Sair" de um canal do WhatsApp,
     * pois ele é adicionado automaticamente. Ele pode, no entanto, "Desafixar".
     */
    get canLeave() {
        if (this.channel_type === "whatsapp") {
            return false;
        }
        return super.canLeave;
    },

    /**
     * Permite que um usuário desafixe um canal do WhatsApp para ocultá-lo da barra lateral.
     * A lógica do `aos_whatsapp` é uma boa prática: só permite desafixar se não houver
     * mensagens não lidas, evitando que o usuário perca conversas ativas.
     */
    get canUnpin() {
        if (this.channel_type === "whatsapp") {
            // `importantCounter` é o contador de mensagens não lidas/necessitando ação.
            return this.importantCounter === 0;
        }
        return super.canUnpin;
    },
    // ============================ FIM DA NOVA ADIÇÃO ============================
});