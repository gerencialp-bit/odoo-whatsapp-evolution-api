/** @odoo-module **/

import { Chatter } from "@mail/chatter/chatter";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(Chatter.prototype, {
    
    /**
     * Handles the click on the 'Send WhatsApp' button.
     * Opens a wizard to compose and send a WhatsApp message.
     */
    async _onClickSendWhatsapp() {
        // Ensure the record is saved before opening the wizard
        const saved = await this.props.saveRecord?.();
        if (!saved && this.props.saveRecord) {
            return;
        }

        this.env.services.action.doAction({
            type: "ir.actions.act_window",
            res_model: "whatsapp.evolution.composer",
            name: _t("Send WhatsApp Message"),
            views: [[false, "form"]],
            target: "new",
            context: {
                active_id: this.thread.id,
                active_model: this.thread.model,
            },
        });
    },
});