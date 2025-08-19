/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";

patch(PosStore.prototype, {
    async add_new_order(...args) {
        // Create the order using the parent method
        const order = await super.add_new_order(...args);
        
        // Ensure the order has a valid fiscal position
        if (!order.fiscal_position_id) {
            const defaultFiscalPosition = this.models["account.fiscal.position"].find(
                position => position.id === this.config.default_fiscal_position_id?.id
            );
            const fallbackFiscalPosition = this.models["account.fiscal.position"].getFirst();
            order.update({ 
                fiscal_position_id: defaultFiscalPosition || fallbackFiscalPosition 
            });
        }

        // Find the SERVICE_FEE product
        const serviceFeeProduct = this.config.pos_service_fee_product_id;
        const serviceFee = this.config.fbr_pos_server_fee;

        
        if (!serviceFeeProduct) {
            console.warn("SERVICE_FEE product not found in POS data.");
            return order;
        }

        // Check if service fee already exists in this order
        const hasServiceFee = order.lines.some(
            line => line.product && line.product.id === serviceFeeProduct.id
        );

        if (!hasServiceFee) {
            try {
                // Create a new order line instance
                const newLine = this.models['pos.order.line'].create({
                    order_id: order,
                    product_id: serviceFeeProduct,
                    qty: 1,
                    price_unit: serviceFee,
                    price_extra: 0,
                    discount: 0,
                    tax_ids: serviceFeeProduct.taxes_id,
                });
                
                // Add the line to the order's lines array
                // order.lines.push(newLine);
                
                // Recompute order totals
                order.recomputeOrderData();
                
                console.log("Service fee added successfully");
            } catch (err) {
                console.error("Failed to add SERVICE_FEE product:", err);
            }
        }

        return order;
    },
});