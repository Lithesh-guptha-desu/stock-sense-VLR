import sqlite3
from database import get_db

class StockEngineError(Exception):
    """Custom exception for inventory stock engine business rule failures."""
    pass

class StockEngine:
    @staticmethod
    def get_stock(product_id, location_id):
        """Retrieve current stock quantity for a product at a specific location."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT quantity FROM stock WHERE product_id = ? AND location_id = ?", (product_id, location_id))
        row = cursor.fetchone()
        conn.close()
        return row['quantity'] if row else 0

    @staticmethod
    def get_product_total_stock(product_id):
        """Retrieve total stock quantity across all locations for a product."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(quantity) as total FROM stock WHERE product_id = ?", (product_id,))
        row = cursor.fetchone()
        conn.close()
        return row['total'] if row and row['total'] is not None else 0

    @staticmethod
    def validate_receipt(receipt_id, user_id=1):
        """
        Validates an incoming Receipt:
        1. Checks receipt status is not already DONE or CANCELED.
        2. Increases stock for each item in receipt at specified location.
        3. Logs each item movement in stock_ledger (RECEIPT).
        4. Updates receipt status to DONE and sets validated_at.
        """
        conn = get_db()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT * FROM receipts WHERE id = ?", (receipt_id,))
            receipt = cursor.fetchone()
            if not receipt:
                raise StockEngineError("Receipt not found.")
            if receipt['status'] in ('DONE', 'CANCELED'):
                raise StockEngineError(f"Receipt is already {receipt['status']}.")

            cursor.execute("SELECT ri.*, p.sku FROM receipt_items ri JOIN products p ON ri.product_id = p.id WHERE ri.receipt_id = ?", (receipt_id,))
            items = cursor.fetchall()
            if not items:
                raise StockEngineError("Receipt contains no product items.")

            for item in items:
                prod_id = item['product_id']
                loc_id = item['location_id']
                qty = item['quantity']
                sku = item['sku']

                # Get current stock
                cursor.execute("SELECT quantity FROM stock WHERE product_id = ? AND location_id = ?", (prod_id, loc_id))
                stock_row = cursor.fetchone()
                prev_qty = stock_row['quantity'] if stock_row else 0
                new_qty = prev_qty + qty

                if stock_row:
                    cursor.execute("UPDATE stock SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE product_id = ? AND location_id = ?",
                                   (new_qty, prod_id, loc_id))
                else:
                    cursor.execute("INSERT INTO stock (product_id, location_id, quantity) VALUES (?, ?, ?)",
                                   (prod_id, loc_id, new_qty))

                # Write to stock_ledger
                cursor.execute('''
                INSERT INTO stock_ledger (product_id, sku, operation_type, reference_id, source_location_id, destination_location_id, quantity, previous_quantity, new_quantity, user_id)
                VALUES (?, ?, 'RECEIPT', ?, NULL, ?, ?, ?, ?, ?)
                ''', (prod_id, sku, receipt['reference_number'], loc_id, qty, prev_qty, new_qty, user_id))

            # Mark receipt DONE
            cursor.execute("UPDATE receipts SET status = 'DONE', validated_at = CURRENT_TIMESTAMP WHERE id = ?", (receipt_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def validate_delivery(delivery_id, user_id=1):
        """
        Validates an outgoing Delivery Order:
        1. Verifies delivery status is not DONE or CANCELED.
        2. Checks available stock at specified location for all items. Prevents deduction if stock < quantity.
        3. Decreases stock for each item.
        4. Logs movement in stock_ledger (DELIVERY).
        5. Updates delivery status to DONE.
        """
        conn = get_db()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT * FROM deliveries WHERE id = ?", (delivery_id,))
            delivery = cursor.fetchone()
            if not delivery:
                raise StockEngineError("Delivery order not found.")
            if delivery['status'] in ('DONE', 'CANCELED'):
                raise StockEngineError(f"Delivery order is already {delivery['status']}.")

            cursor.execute("SELECT di.*, p.sku, p.name as product_name FROM delivery_items di JOIN products p ON di.product_id = p.id WHERE di.delivery_id = ?", (delivery_id,))
            items = cursor.fetchall()
            if not items:
                raise StockEngineError("Delivery contains no product items.")

            # First pass: Validate stock sufficiency
            for item in items:
                prod_id = item['product_id']
                loc_id = item['location_id']
                req_qty = item['quantity']

                cursor.execute("SELECT quantity FROM stock WHERE product_id = ? AND location_id = ?", (prod_id, loc_id))
                stock_row = cursor.fetchone()
                current_qty = stock_row['quantity'] if stock_row else 0

                if current_qty < req_qty:
                    raise StockEngineError(
                        f"Insufficient stock for {item['product_name']} (SKU: {item['sku']}) at location. Available: {current_qty}, Requested: {req_qty}"
                    )

            # Second pass: Process stock reduction & ledger
            for item in items:
                prod_id = item['product_id']
                loc_id = item['location_id']
                req_qty = item['quantity']
                sku = item['sku']

                cursor.execute("SELECT quantity FROM stock WHERE product_id = ? AND location_id = ?", (prod_id, loc_id))
                prev_qty = cursor.fetchone()['quantity']
                new_qty = prev_qty - req_qty

                cursor.execute("UPDATE stock SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE product_id = ? AND location_id = ?",
                               (new_qty, prod_id, loc_id))

                cursor.execute('''
                INSERT INTO stock_ledger (product_id, sku, operation_type, reference_id, source_location_id, destination_location_id, quantity, previous_quantity, new_quantity, user_id)
                VALUES (?, ?, 'DELIVERY', ?, ?, NULL, ?, ?, ?, ?)
                ''', (prod_id, sku, delivery['reference_number'], loc_id, -req_qty, prev_qty, new_qty, user_id))

            cursor.execute("UPDATE deliveries SET status = 'DONE', validated_at = CURRENT_TIMESTAMP WHERE id = ?", (delivery_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def validate_transfer(transfer_id, user_id=1):
        """
        Validates an Internal Transfer:
        1. Checks transfer status is not DONE or CANCELED.
        2. Deducts quantity from source location (verifying sufficient stock).
        3. Adds quantity to destination location.
        4. Logs entry in stock_ledger (INTERNAL TRANSFER).
        5. Updates transfer status to DONE. Total company stock remains constant.
        """
        conn = get_db()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT * FROM transfers WHERE id = ?", (transfer_id,))
            transfer = cursor.fetchone()
            if not transfer:
                raise StockEngineError("Transfer order not found.")
            if transfer['status'] in ('DONE', 'CANCELED'):
                raise StockEngineError(f"Transfer is already {transfer['status']}.")

            src_loc = transfer['source_location_id']
            dst_loc = transfer['destination_location_id']

            cursor.execute("SELECT ti.*, p.sku, p.name as product_name FROM transfer_items ti JOIN products p ON ti.product_id = p.id WHERE ti.transfer_id = ?", (transfer_id,))
            items = cursor.fetchall()
            if not items:
                raise StockEngineError("Transfer contains no product items.")

            # Validate source stock
            for item in items:
                prod_id = item['product_id']
                qty = item['quantity']

                cursor.execute("SELECT quantity FROM stock WHERE product_id = ? AND location_id = ?", (prod_id, src_loc))
                stock_row = cursor.fetchone()
                src_qty = stock_row['quantity'] if stock_row else 0

                if src_qty < qty:
                    raise StockEngineError(
                        f"Insufficient stock for transfer of {item['product_name']} at source location. Available: {src_qty}, Transfer qty: {qty}"
                    )

            # Process transfer
            for item in items:
                prod_id = item['product_id']
                qty = item['quantity']
                sku = item['sku']

                # Deduct from source
                cursor.execute("SELECT quantity FROM stock WHERE product_id = ? AND location_id = ?", (prod_id, src_loc))
                src_prev = cursor.fetchone()['quantity']
                src_new = src_prev - qty
                cursor.execute("UPDATE stock SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE product_id = ? AND location_id = ?",
                               (src_new, prod_id, src_loc))

                # Add to destination
                cursor.execute("SELECT quantity FROM stock WHERE product_id = ? AND location_id = ?", (prod_id, dst_loc))
                dst_row = cursor.fetchone()
                dst_prev = dst_row['quantity'] if dst_row else 0
                dst_new = dst_prev + qty

                if dst_row:
                    cursor.execute("UPDATE stock SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE product_id = ? AND location_id = ?",
                                   (dst_new, prod_id, dst_loc))
                else:
                    cursor.execute("INSERT INTO stock (product_id, location_id, quantity) VALUES (?, ?, ?)",
                                   (prod_id, dst_loc, dst_new))

                # Ledger entry
                cursor.execute('''
                INSERT INTO stock_ledger (product_id, sku, operation_type, reference_id, source_location_id, destination_location_id, quantity, previous_quantity, new_quantity, user_id)
                VALUES (?, ?, 'INTERNAL TRANSFER', ?, ?, ?, ?, ?, ?, ?)
                ''', (prod_id, sku, transfer['reference_number'], src_loc, dst_loc, qty, src_prev, src_new, user_id))

            cursor.execute("UPDATE transfers SET status = 'DONE', completed_at = CURRENT_TIMESTAMP WHERE id = ?", (transfer_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def validate_adjustment(product_id, location_id, physical_quantity, reason="Physical Count Audit", user_id=1):
        """
        Validates an Inventory Adjustment:
        1. Compares system stock with physical_quantity.
        2. Calculates difference = physical_quantity - system_quantity.
        3. Updates stock quantity to physical_quantity.
        4. Logs entry in stock_ledger (ADJUSTMENT).
        5. Inserts row into adjustments table.
        """
        conn = get_db()
        cursor = conn.cursor()

        try:
            # Check product & sku
            cursor.execute("SELECT sku, name FROM products WHERE id = ?", (product_id,))
            prod = cursor.fetchone()
            if not prod:
                raise StockEngineError("Product not found.")

            cursor.execute("SELECT quantity FROM stock WHERE product_id = ? AND location_id = ?", (product_id, location_id))
            stock_row = cursor.fetchone()
            sys_qty = stock_row['quantity'] if stock_row else 0
            diff = physical_quantity - sys_qty

            if stock_row:
                cursor.execute("UPDATE stock SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE product_id = ? AND location_id = ?",
                               (physical_quantity, product_id, location_id))
            else:
                cursor.execute("INSERT INTO stock (product_id, location_id, quantity) VALUES (?, ?, ?)",
                               (product_id, location_id, physical_quantity))

            # Reference number for adjustment
            cursor.execute("SELECT COUNT(*) FROM adjustments")
            adj_count = cursor.fetchone()[0] + 1
            ref_no = f"ADJ-{5000 + adj_count}"

            # Create adjustment record
            cursor.execute('''
            INSERT INTO adjustments (reference_number, product_id, location_id, system_quantity, physical_quantity, difference, reason, status, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'DONE', ?)
            ''', (ref_no, product_id, location_id, sys_qty, physical_quantity, diff, reason, user_id))

            # Ledger entry
            cursor.execute('''
            INSERT INTO stock_ledger (product_id, sku, operation_type, reference_id, source_location_id, destination_location_id, quantity, previous_quantity, new_quantity, user_id)
            VALUES (?, ?, 'ADJUSTMENT', ?, ?, ?, ?, ?, ?, ?)
            ''', (product_id, prod['sku'], ref_no, location_id, location_id, diff, sys_qty, physical_quantity, user_id))

            conn.commit()
            return {
                "reference_number": ref_no,
                "previous_quantity": sys_qty,
                "new_quantity": physical_quantity,
                "difference": diff
            }
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
