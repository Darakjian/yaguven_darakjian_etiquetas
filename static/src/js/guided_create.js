/** @odoo-module **/

/* The New button on the product views opens the guided wizard instead of the bare form.
 *
 * Why intercept it rather than add a second entry point: whoever loads a product will use
 * the button that is there, not the one further down the menu. If the guided path is a
 * separate menu item it simply does not get used, and the loading stays as it is -- 81%
 * of the watches printing one cell or none.
 *
 * A family with no setup yet opens the wizard with no attribute lines and creates the
 * product all the same, so nothing that can be loaded today stops being loadable. */

import { status } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { useService } from "@web/core/utils/hooks";

const WIZARD = "yaguven_darakjian_etiquetas.action_yag_product_wizard";

/* The wizard finishes by returning an action of its own -- the product it has just
 * created -- and that action replaces the view this button was pressed from, which
 * destroys it. Reloading from here without looking first asks a dead component's ORM for
 * records, and it answers "Component is destroyed": the person gets an error thrown over
 * a product that WAS created, does not believe it, and loads it a second time. That is
 * where the four duplicate pairs of the 2026-09-11 QA came from -- each twin carrying the
 * same internal reference as the other, which is the part that hurts later.
 *
 * On Cancel the view behind is still alive and reloading is exactly the point, so the
 * guard goes on the status of the component and not on dropping the callback. */
function abrirWizardGuiado(controller) {
    return controller.actionService.doAction(WIZARD, {
        onClose: () => {
            if (status(controller) !== "destroyed") {
                controller.model.load();
            }
        },
    });
}

class GuidedListController extends ListController {
    setup() {
        super.setup();
        this.actionService = useService("action");
    }
    async createRecord() {
        return abrirWizardGuiado(this);
    }
}

class GuidedKanbanController extends KanbanController {
    setup() {
        super.setup();
        this.actionService = useService("action");
    }
    async createRecord() {
        return abrirWizardGuiado(this);
    }
}

registry.category("views").add("product_guided_list", {
    ...listView,
    Controller: GuidedListController,
});
registry.category("views").add("product_guided_kanban", {
    ...kanbanView,
    Controller: GuidedKanbanController,
});
