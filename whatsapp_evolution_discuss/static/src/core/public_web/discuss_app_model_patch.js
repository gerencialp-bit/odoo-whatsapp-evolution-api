/** @odoo-module **/

import { DiscussApp } from "@mail/core/public_web/discuss_app_model";
import { Record } from "@mail/core/common/record";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(DiscussApp, {
    // Adds the 'whatsapp' category to the DiscussApp model definition.
    new(data) {
        const res = super.new(data);
        res.whatsapp = {
            id: "whatsapp",
            name: _t("WhatsApp"),
            serverStateKey: "is_discuss_sidebar_category_whatsapp_open",
            canView: true,
            canAdd: true,
            addTitle: _t("Start a conversation"),
            sequence: 25, // Position after 'Channels' and 'Chats'
        };
        return res;
    },
});

patch(DiscussApp.prototype, {
    // Initializes the 'whatsapp' category as a record.
    setup(env) {
        super.setup(env);
        this.whatsapp = Record.one("DiscussAppCategory");
    },
});