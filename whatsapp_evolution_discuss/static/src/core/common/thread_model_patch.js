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
});