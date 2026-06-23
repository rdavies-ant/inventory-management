from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
from mock_data import inventory_items, orders, demand_forecasts, backlog_items, spending_summary, monthly_spending, category_spending, recent_transactions, purchase_orders

app = FastAPI(title="Factory Inventory Management System")

# Quarter mapping for date filtering
QUARTER_MAP = {
    'Q1-2025': ['2025-01', '2025-02', '2025-03'],
    'Q2-2025': ['2025-04', '2025-05', '2025-06'],
    'Q3-2025': ['2025-07', '2025-08', '2025-09'],
    'Q4-2025': ['2025-10', '2025-11', '2025-12']
}

def filter_by_month(items: list, month: Optional[str]) -> list:
    """Filter items by month/quarter based on order_date field"""
    if not month or month == 'all':
        return items

    if month.startswith('Q'):
        # Handle quarters
        if month in QUARTER_MAP:
            months = QUARTER_MAP[month]
            return [item for item in items if any(m in item.get('order_date', '') for m in months)]
    else:
        # Direct month match
        return [item for item in items if month in item.get('order_date', '')]

    return items

def apply_filters(items: list, warehouse: Optional[str] = None, category: Optional[str] = None,
                 status: Optional[str] = None) -> list:
    """Apply common filters to a list of items"""
    filtered = items

    if warehouse and warehouse != 'all':
        filtered = [item for item in filtered if item.get('warehouse') == warehouse]

    if category and category != 'all':
        filtered = [item for item in filtered if item.get('category', '').lower() == category.lower()]

    if status and status != 'all':
        filtered = [item for item in filtered if item.get('status', '').lower() == status.lower()]

    return filtered

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data models
class InventoryItem(BaseModel):
    id: str
    sku: str
    name: str
    category: str
    warehouse: str
    quantity_on_hand: int
    reorder_point: int
    unit_cost: float
    location: str
    last_updated: str

class Order(BaseModel):
    id: str
    order_number: str
    customer: str
    items: List[dict]
    status: str
    order_date: str
    expected_delivery: str
    total_value: float
    actual_delivery: Optional[str] = None
    warehouse: Optional[str] = None
    category: Optional[str] = None
    # Restocking orders (placed from the Restocking tab) are flagged with
    # source="restocking" and carry a lead time so the Orders page can
    # surface them in a dedicated "Submitted Orders" section.
    source: Optional[str] = None
    lead_time_days: Optional[int] = None

class DemandForecast(BaseModel):
    id: str
    item_sku: str
    item_name: str
    current_demand: int
    forecasted_demand: int
    trend: str
    period: str

class BacklogItem(BaseModel):
    id: str
    order_id: str
    item_sku: str
    item_name: str
    quantity_needed: int
    quantity_available: int
    days_delayed: int
    priority: str
    has_purchase_order: Optional[bool] = False

class PurchaseOrder(BaseModel):
    id: str
    backlog_item_id: str
    supplier_name: str
    quantity: int
    unit_cost: float
    expected_delivery_date: str
    status: str
    created_date: str
    notes: Optional[str] = None

class CreatePurchaseOrderRequest(BaseModel):
    backlog_item_id: str
    supplier_name: str
    quantity: int
    unit_cost: float
    expected_delivery_date: str
    notes: Optional[str] = None

class RestockRecommendation(BaseModel):
    sku: str
    name: str
    warehouse: str
    category: str
    current_demand: int
    forecasted_demand: int
    trend: str
    unit_cost: float
    suggested_quantity: int
    suggested_cost: float
    partial: bool = False

class RestockSummary(BaseModel):
    budget: float
    total_recommended_cost: float
    remaining_budget: float
    recommendations: List[RestockRecommendation]

class RestockOrderItem(BaseModel):
    sku: str
    name: str
    quantity: int
    unit_cost: float

class PlaceRestockOrderRequest(BaseModel):
    budget: float
    items: List[RestockOrderItem]

# API endpoints
@app.get("/")
def root():
    return {"message": "Factory Inventory Management System API", "version": "1.0.0"}

@app.get("/api/inventory", response_model=List[InventoryItem])
def get_inventory(
    warehouse: Optional[str] = None,
    category: Optional[str] = None
):
    """Get all inventory items with optional filtering"""
    return apply_filters(inventory_items, warehouse, category)

@app.get("/api/inventory/{item_id}", response_model=InventoryItem)
def get_inventory_item(item_id: str):
    """Get a specific inventory item"""
    item = next((item for item in inventory_items if item["id"] == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@app.get("/api/orders", response_model=List[Order])
def get_orders(
    warehouse: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    month: Optional[str] = None
):
    """Get all orders with optional filtering"""
    filtered_orders = apply_filters(orders, warehouse, category, status)
    filtered_orders = filter_by_month(filtered_orders, month)
    return filtered_orders

@app.get("/api/orders/{order_id}", response_model=Order)
def get_order(order_id: str):
    """Get a specific order"""
    order = next((order for order in orders if order["id"] == order_id), None)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@app.get("/api/demand", response_model=List[DemandForecast])
def get_demand_forecasts():
    """Get demand forecasts"""
    return demand_forecasts

@app.get("/api/backlog", response_model=List[BacklogItem])
def get_backlog():
    """Get backlog items with purchase order status"""
    # Add has_purchase_order flag to each backlog item
    result = []
    for item in backlog_items:
        item_dict = dict(item)
        # Check if this backlog item has a purchase order
        has_po = any(po["backlog_item_id"] == item["id"] for po in purchase_orders)
        item_dict["has_purchase_order"] = has_po
        result.append(item_dict)
    return result

@app.get("/api/dashboard/summary")
def get_dashboard_summary(
    warehouse: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    month: Optional[str] = None
):
    """Get summary statistics for dashboard with optional filtering"""
    # Filter inventory
    filtered_inventory = apply_filters(inventory_items, warehouse, category)

    # Filter orders
    filtered_orders = apply_filters(orders, warehouse, category, status)
    filtered_orders = filter_by_month(filtered_orders, month)

    total_inventory_value = sum(item["quantity_on_hand"] * item["unit_cost"] for item in filtered_inventory)
    low_stock_items = len([item for item in filtered_inventory if item["quantity_on_hand"] <= item["reorder_point"]])
    pending_orders = len([order for order in filtered_orders if order["status"] in ["Processing", "Backordered"]])
    total_backlog_items = len(backlog_items)

    return {
        "total_inventory_value": round(total_inventory_value, 2),
        "low_stock_items": low_stock_items,
        "pending_orders": pending_orders,
        "total_backlog_items": total_backlog_items,
        "total_orders_value": sum(order["total_value"] for order in filtered_orders)
    }

@app.get("/api/spending/summary")
def get_spending_summary():
    """Get spending summary statistics"""
    return spending_summary

@app.get("/api/spending/monthly")
def get_monthly_spending():
    """Get monthly spending breakdown"""
    return monthly_spending

@app.get("/api/spending/categories")
def get_category_spending():
    """Get spending by category"""
    return category_spending

@app.get("/api/spending/transactions")
def get_recent_transactions():
    """Get recent transactions"""
    return recent_transactions

@app.get("/api/reports/quarterly")
def get_quarterly_reports(
    warehouse: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    month: Optional[str] = None
):
    """Get quarterly performance reports (honors the global filter bar)"""
    # Apply the same global filters the rest of the app uses so the Reports
    # page responds to the filter bar like every other page.
    filtered_orders = apply_filters(orders, warehouse, category, status)
    filtered_orders = filter_by_month(filtered_orders, month)

    # Calculate quarterly statistics from orders
    quarters = {}

    for order in filtered_orders:
        order_date = order.get('order_date', '')
        # Determine quarter
        if '2025-01' in order_date or '2025-02' in order_date or '2025-03' in order_date:
            quarter = 'Q1-2025'
        elif '2025-04' in order_date or '2025-05' in order_date or '2025-06' in order_date:
            quarter = 'Q2-2025'
        elif '2025-07' in order_date or '2025-08' in order_date or '2025-09' in order_date:
            quarter = 'Q3-2025'
        elif '2025-10' in order_date or '2025-11' in order_date or '2025-12' in order_date:
            quarter = 'Q4-2025'
        else:
            continue

        if quarter not in quarters:
            quarters[quarter] = {
                'quarter': quarter,
                'total_orders': 0,
                'total_revenue': 0,
                'delivered_orders': 0,
                'avg_order_value': 0
            }

        quarters[quarter]['total_orders'] += 1
        quarters[quarter]['total_revenue'] += order.get('total_value', 0)
        if order.get('status') == 'Delivered':
            quarters[quarter]['delivered_orders'] += 1

    # Calculate averages and fulfillment rate
    result = []
    for q, data in quarters.items():
        if data['total_orders'] > 0:
            data['avg_order_value'] = round(data['total_revenue'] / data['total_orders'], 2)
            data['fulfillment_rate'] = round((data['delivered_orders'] / data['total_orders']) * 100, 1)
        result.append(data)

    # Sort by quarter
    result.sort(key=lambda x: x['quarter'])
    return result

@app.get("/api/reports/monthly-trends")
def get_monthly_trends(
    warehouse: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    month: Optional[str] = None
):
    """Get month-over-month trends (honors the global filter bar)"""
    filtered_orders = apply_filters(orders, warehouse, category, status)
    filtered_orders = filter_by_month(filtered_orders, month)

    months = {}

    for order in filtered_orders:
        order_date = order.get('order_date', '')
        if not order_date:
            continue

        # Extract month (format: YYYY-MM-DD)
        month = order_date[:7]  # Gets YYYY-MM

        if month not in months:
            months[month] = {
                'month': month,
                'order_count': 0,
                'revenue': 0,
                'delivered_count': 0
            }

        months[month]['order_count'] += 1
        months[month]['revenue'] += order.get('total_value', 0)
        if order.get('status') == 'Delivered':
            months[month]['delivered_count'] += 1

    # Convert to list and sort
    result = list(months.values())
    result.sort(key=lambda x: x['month'])
    return result

@app.get("/api/restocking/recommendations", response_model=RestockSummary)
def get_restock_recommendations(
    budget: float,
    warehouse: Optional[str] = None,
    category: Optional[str] = None
):
    """Recommend items to restock within a budget, based on demand forecast data.

    Strategy: join each demand forecast to its inventory item (by SKU) to get
    unit cost and current stock context. Only items with a forecasted demand
    gap (forecasted > current) are candidates - that gap is the suggested
    restock quantity. Candidates are prioritized "increasing" trend first,
    then by cheapest subtotal, so the budget is spent on the most urgent and
    most efficient restocks first (a simple greedy knapsack). If the budget
    runs out partway through an item, a partial quantity is suggested so the
    full budget is put to use.
    """
    if budget < 0:
        raise HTTPException(status_code=400, detail="Budget must be non-negative")

    inventory_by_sku = {item["sku"]: item for item in inventory_items}

    candidates = []
    for forecast in demand_forecasts:
        item = inventory_by_sku.get(forecast["item_sku"])
        if not item:
            continue
        if warehouse and warehouse != "all" and item.get("warehouse") != warehouse:
            continue
        if category and category != "all" and item.get("category", "").lower() != category.lower():
            continue

        gap = forecast["forecasted_demand"] - forecast["current_demand"]
        if gap <= 0:
            continue

        candidates.append({
            "sku": forecast["item_sku"],
            "name": forecast["item_name"],
            "warehouse": item["warehouse"],
            "category": item["category"],
            "current_demand": forecast["current_demand"],
            "forecasted_demand": forecast["forecasted_demand"],
            "trend": forecast["trend"],
            "unit_cost": item["unit_cost"],
            "quantity": gap,
        })

    # Priority: increasing trend first, then cheapest subtotal first (covers
    # the most distinct SKUs per dollar of budget).
    trend_rank = {"increasing": 0, "stable": 1, "decreasing": 2}
    candidates.sort(key=lambda c: (trend_rank.get(c["trend"], 3), c["quantity"] * c["unit_cost"]))

    recommendations = []
    remaining_budget = round(budget, 2)
    total_recommended_cost = 0.0

    for c in candidates:
        if remaining_budget <= 0:
            break

        full_cost = round(c["quantity"] * c["unit_cost"], 2)
        if full_cost <= remaining_budget:
            quantity = c["quantity"]
            cost = full_cost
            partial = False
        else:
            quantity = int(remaining_budget // c["unit_cost"])
            if quantity <= 0:
                continue
            cost = round(quantity * c["unit_cost"], 2)
            partial = True

        recommendations.append(RestockRecommendation(
            sku=c["sku"],
            name=c["name"],
            warehouse=c["warehouse"],
            category=c["category"],
            current_demand=c["current_demand"],
            forecasted_demand=c["forecasted_demand"],
            trend=c["trend"],
            unit_cost=c["unit_cost"],
            suggested_quantity=quantity,
            suggested_cost=cost,
            partial=partial,
        ))
        remaining_budget = round(remaining_budget - cost, 2)
        total_recommended_cost = round(total_recommended_cost + cost, 2)

    return RestockSummary(
        budget=budget,
        total_recommended_cost=total_recommended_cost,
        remaining_budget=remaining_budget,
        recommendations=recommendations,
    )

@app.post("/api/restocking/orders", response_model=Order)
def place_restock_order(request: PlaceRestockOrderRequest):
    """Submit a restocking order built from the Restocking tab's recommendations.

    Creates a new entry in the in-memory `orders` list (flagged
    source="restocking") so it shows up immediately in the Orders tab's
    "Submitted Orders" section, complete with an estimated delivery lead time.
    """
    if not request.items:
        raise HTTPException(status_code=400, detail="At least one item is required")

    # Resolve the authoritative unit cost / name / category / warehouse from
    # inventory on the server - never trust client-supplied prices, since
    # total_value (and the derived lead time) are computed from them. Unknown
    # SKUs are rejected.
    inventory_by_sku = {item["sku"]: item for item in inventory_items}
    resolved_items = []
    for item in request.items:
        inv = inventory_by_sku.get(item.sku)
        if not inv:
            raise HTTPException(status_code=400, detail=f"Unknown SKU: {item.sku}")
        resolved_items.append({
            "sku": item.sku,
            "name": inv["name"],
            "quantity": item.quantity,
            "unit_price": inv["unit_cost"],
            "category": inv["category"],
            "warehouse": inv["warehouse"],
        })

    total_value = round(sum(i["quantity"] * i["unit_price"] for i in resolved_items), 2)

    # Simple deterministic lead time: a 5-day baseline plus 1 extra day per
    # $5,000 of order value (bigger restocks take longer to fulfill/ship),
    # capped at 21 days.
    lead_time_days = min(5 + int(total_value // 5000), 21)

    now = datetime.now()
    expected_delivery = now + timedelta(days=lead_time_days)
    restock_count = len([o for o in orders if o.get("source") == "restocking"])
    order_number = f"RESTOCK-{restock_count + 1:04d}"

    # Use the most common category / warehouse among the ordered items for display.
    categories = [i["category"] for i in resolved_items]
    category = max(set(categories), key=categories.count) if categories else None
    warehouses = [i["warehouse"] for i in resolved_items]
    warehouse = max(set(warehouses), key=warehouses.count) if warehouses else None

    new_order = {
        "id": str(len(orders) + 1),
        "order_number": order_number,
        "customer": "Internal Restocking",
        "items": [
            {"sku": i["sku"], "name": i["name"], "quantity": i["quantity"], "unit_price": i["unit_price"]}
            for i in resolved_items
        ],
        "status": "Processing",
        "order_date": now.isoformat(),
        "expected_delivery": expected_delivery.isoformat(),
        "total_value": total_value,
        "actual_delivery": None,
        "warehouse": warehouse,
        "category": category,
        "source": "restocking",
        "lead_time_days": lead_time_days,
    }
    orders.append(new_order)
    return new_order

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
