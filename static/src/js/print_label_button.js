/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

// 127.0.0.1 y NO "localhost": en macOS "localhost" resuelve primero a ::1 (IPv6) y el
// bridge escucha solo en IPv4 (`ZBRIDGE_LISTEN_HOST` por defecto en 127.0.0.1). Verificado
// en el iMac de la tienda: por 127.0.0.1 responde 200, por [::1] no responde nada. curl
// disimula el problema porque reintenta con IPv4; el navegador no siempre lo hace, y el
// sintoma es un "Failed to fetch" pelado que no dice de que se trata.
const BRIDGE_URL = "http://127.0.0.1:9199/write";

class PrintJewelryLabelButton extends Component {
    static template = "yaguven_darakjian_etiquetas.PrintLabelButton";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({ printing: false });
    }

    async onClick() {
        const resId = this.props.record.resId;
        if (!resId) {
            return;
        }
        this.state.printing = true;
        try {
            const zpl = await this.orm.call(
                "product.product",
                "get_jewelry_label_zpl",
                [[resId]]
            );
            const response = await fetch(BRIDGE_URL, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ data: zpl }),
            });
            if (!response.ok) {
                throw new Error(await response.text());
            }
            this.notification.add("Tag sent to the Zebra printer", {
                type: "success",
            });
        } catch (error) {
            this.notification.add("Could not print: " + error.message, {
                type: "danger",
            });
        } finally {
            this.state.printing = false;
        }
    }
}

registry.category("view_widgets").add("print_jewelry_label", {
    component: PrintJewelryLabelButton,
});
