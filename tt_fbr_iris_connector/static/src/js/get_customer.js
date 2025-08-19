import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { patch } from "@web/core/utils/patch";

patch(ReceiptScreen.prototype, {
    setup() {
        super.setup();
        const order = this.currentOrder;
        console.log("Field in Receipt Screen:", order.fbr_invoice_number);
        console.log("Field in Receipt Screen:", order.partner_id);
    },
});