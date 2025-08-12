from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

from sqlalchemy import func, extract, and_

from common.database import db
from models.shop.shop_order import ShopOrder, ShopOrderItem
from models.shop.shop_product import ShopProduct
from models.shop.shop_category import ShopCategory


class ShopAnalyticsController:
    """Shop-specific analytics (superadmin)."""

    @staticmethod
    def _period_range(months: int) -> Tuple[datetime, datetime]:
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=30 * max(1, int(months)))
        return start_date, end_date

    @staticmethod
    def _month_range(year: int, month: int) -> Tuple[datetime, datetime]:
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
        return start, end

    @staticmethod
    def summary(shop_id: int, months: int = 6):
        start_date, end_date = ShopAnalyticsController._period_range(months)

        totals = db.session.query(
            func.sum(ShopOrder.total_amount).label('revenue'),
            func.count(func.distinct(ShopOrder.order_id)).label('orders')
        ).filter(
            ShopOrder.shop_id == shop_id,
            ShopOrder.order_date >= start_date,
            ShopOrder.order_date <= end_date
        ).first()

        revenue = float(totals.revenue or 0)
        orders = int(totals.orders or 0)

        total_sold = db.session.query(
            func.coalesce(func.sum(ShopOrderItem.quantity), 0)
        ).join(ShopOrder, ShopOrder.order_id == ShopOrderItem.order_id).filter(
            ShopOrderItem.shop_id == shop_id,
            ShopOrder.order_date >= start_date,
            ShopOrder.order_date <= end_date
        ).scalar() or 0

        total_sold = int(total_sold)

        top_product_row = db.session.query(
            ShopOrderItem.product_name_at_purchase.label('name'),
            func.sum(ShopOrderItem.quantity).label('sold')
        ).join(ShopOrder, ShopOrder.order_id == ShopOrderItem.order_id).filter(
            ShopOrderItem.shop_id == shop_id,
            ShopOrder.order_date >= start_date,
            ShopOrder.order_date <= end_date
        ).group_by(ShopOrderItem.product_name_at_purchase).order_by(func.sum(ShopOrderItem.quantity).desc()).first()

        top_product = top_product_row.name if top_product_row else None

        top_category_row = db.session.query(
            ShopCategory.name.label('category_name'),
            func.sum(ShopOrderItem.quantity).label('sold')
        ).join(ShopProduct, ShopProduct.product_id == ShopOrderItem.product_id)
        top_category_row = top_category_row.join(ShopCategory, ShopCategory.category_id == ShopProduct.category_id)
        top_category_row = top_category_row.join(ShopOrder, ShopOrder.order_id == ShopOrderItem.order_id)
        top_category_row = top_category_row.filter(
            ShopOrderItem.shop_id == shop_id,
            ShopOrder.order_date >= start_date,
            ShopOrder.order_date <= end_date
        ).group_by(ShopCategory.name).order_by(func.sum(ShopOrderItem.quantity).desc()).first()

        top_category = top_category_row.category_name if top_category_row else None

        aov = round(revenue / orders, 2) if orders > 0 else 0.0

        return {
            "status": "success",
            "data": {
                "revenue": revenue,
                "total_sold": total_sold,
                "top_product": top_product,
                "top_category": top_category,
                "average_order_value": aov,
                "currency": "INR"
            }
        }

    @staticmethod
    def revenue_trend(shop_id: int, months: int = 6):
        start_date, end_date = ShopAnalyticsController._period_range(months)
        rows = db.session.query(
            extract('year', ShopOrder.order_date).label('year'),
            extract('month', ShopOrder.order_date).label('month'),
            func.sum(ShopOrderItem.line_item_total_inclusive_gst).label('revenue'),
            func.count(func.distinct(ShopOrder.order_id)).label('orders')
        ).join(ShopOrderItem, ShopOrderItem.order_id == ShopOrder.order_id).filter(
            ShopOrder.shop_id == shop_id,
            ShopOrder.order_date >= start_date,
            ShopOrder.order_date <= end_date
        ).group_by(
            extract('year', ShopOrder.order_date),
            extract('month', ShopOrder.order_date)
        ).order_by(
            extract('year', ShopOrder.order_date),
            extract('month', ShopOrder.order_date)
        ).all()

        trend = []
        for r in rows:
            month_label = f"{int(r.year)}-{int(r.month):02d}"
            rev = float(r.revenue or 0)
            orders = int(r.orders or 0)
            trend.append({
                "month": month_label,
                "revenue": rev,
                "orders": orders,
                "average_order_value": round(rev / orders, 2) if orders > 0 else 0.0
            })

        return {"status": "success", "data": {"trend": trend, "currency": "INR"}}

    @staticmethod
    def product_sales(shop_id: int, year: Optional[int] = None, month: Optional[int] = None, limit: int = 10):
        if year and month:
            start, end = ShopAnalyticsController._month_range(year, month)
        else:
            start, end = ShopAnalyticsController._period_range(6)

        rows = db.session.query(
            ShopOrderItem.product_name_at_purchase.label('name'),
            func.sum(ShopOrderItem.quantity).label('sold')
        ).join(ShopOrder, ShopOrder.order_id == ShopOrderItem.order_id).filter(
            ShopOrderItem.shop_id == shop_id,
            ShopOrder.order_date >= start,
            ShopOrder.order_date < end
        ).group_by(ShopOrderItem.product_name_at_purchase).order_by(func.sum(ShopOrderItem.quantity).desc()).limit(limit).all()

        data = [{"name": r.name, "sold": int(r.sold or 0)} for r in rows]
        return {"status": "success", "data": data}

    @staticmethod
    def category_distribution(shop_id: int, months: int = 6):
        start, end = ShopAnalyticsController._period_range(months)

        total_items = db.session.query(
            func.coalesce(func.sum(ShopOrderItem.quantity), 0)
        ).join(ShopOrder, ShopOrder.order_id == ShopOrderItem.order_id).filter(
            ShopOrderItem.shop_id == shop_id,
            ShopOrder.order_date >= start,
            ShopOrder.order_date <= end
        ).scalar() or 0

        cat_rows = db.session.query(
            ShopCategory.name.label('name'),
            func.sum(ShopOrderItem.quantity).label('qty')
        ).join(ShopProduct, ShopProduct.product_id == ShopOrderItem.product_id)
        cat_rows = cat_rows.join(ShopCategory, ShopCategory.category_id == ShopProduct.category_id)
        cat_rows = cat_rows.join(ShopOrder, ShopOrder.order_id == ShopOrderItem.order_id)
        cat_rows = cat_rows.filter(
            ShopOrderItem.shop_id == shop_id,
            ShopOrder.order_date >= start,
            ShopOrder.order_date <= end
        ).group_by(ShopCategory.name).order_by(func.sum(ShopOrderItem.quantity).desc()).all()

        data = []
        total_items = int(total_items)
        for r in cat_rows:
            count = int(r.qty or 0)
            pct = round((count / total_items * 100), 1) if total_items > 0 else 0.0
            data.append({"name": r.name, "value": count, "percent": pct})

        return {"status": "success", "data": {"categories": data, "total_items": total_items}}

    @staticmethod
    def export(shop_id: int, year: Optional[int], month: Optional[int], fmt: str = 'csv'):
        try:
            from io import BytesIO
            import pandas as pd
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter, landscape
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch

            if year and month:
                start, end = ShopAnalyticsController._month_range(year, month)
            else:
                start, end = ShopAnalyticsController._period_range(6)

            q = db.session.query(
                ShopOrder.order_date,
                ShopOrder.order_id,
                ShopOrderItem.quantity,
                ShopOrderItem.line_item_total_inclusive_gst.label('amount'),
                ShopOrderItem.product_name_at_purchase.label('product_name')
            ).join(ShopOrder, ShopOrder.order_id == ShopOrderItem.order_id).filter(
                ShopOrder.shop_id == shop_id,
                ShopOrder.order_date >= start,
                ShopOrder.order_date < end
            ).order_by(ShopOrder.order_date.desc())

            rows = q.all()
            import pandas as pd  # noqa: F401 (ensure imported)
            df = pd.DataFrame([
                {
                    'Date': r.order_date.strftime('%Y-%m-%d'),
                    'Order ID': r.order_id,
                    'Product': r.product_name,
                    'Quantity': int(r.quantity or 0),
                    'Amount': float(r.amount or 0.0)
                } for r in rows
            ])

            if df.empty:
                df = pd.DataFrame(columns=['Date', 'Order ID', 'Product', 'Quantity', 'Amount'])

            summary = pd.DataFrame([{
                'Total Orders': df['Order ID'].nunique(),
                'Total Revenue': float(df['Amount'].sum() if not df.empty else 0.0),
                'Total Products Sold': int(df['Quantity'].sum() if not df.empty else 0),
                'Average Order Value': float(df.groupby('Order ID')['Amount'].sum().mean() if not df.empty else 0.0)
            }])

            period_suffix = f"{year}-{month:02d}" if year and month else "last-6-months"
            if fmt == 'csv':
                out = BytesIO()
                df.to_csv(out, index=False)
                out.seek(0)
                return out.getvalue(), 'text/csv', f'shop_{shop_id}_sales_{period_suffix}.csv'
            elif fmt == 'excel':
                out = BytesIO()
                with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
                    df.to_excel(writer, sheet_name='Sales Data', index=False)
                    summary.to_excel(writer, sheet_name='Summary', index=False)
                    wb = writer.book
                    header_fmt = wb.add_format({'bold': True, 'bg_color': '#FF5733', 'font_color': 'white'})
                    for sheet_name in ['Sales Data', 'Summary']:
                        ws = writer.sheets[sheet_name]
                        cols = df.columns if sheet_name == 'Sales Data' else summary.columns
                        for col_idx, value in enumerate(cols):
                            ws.write(0, col_idx, value, header_fmt)
                            ws.set_column(col_idx, col_idx, 20)
                out.seek(0)
                return out.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', f'shop_{shop_id}_sales_{period_suffix}.xlsx'
            elif fmt == 'pdf':
                out = BytesIO()
                doc = SimpleDocTemplate(out, pagesize=landscape(letter), rightMargin=0.5*inch, leftMargin=0.5*inch, topMargin=0.5*inch, bottomMargin=0.5*inch)
                elements = []
                styles = getSampleStyleSheet()
                title_style = ParagraphStyle('Title', parent=styles['Heading1'], textColor=colors.HexColor('#FF5733'))
                elements.append(Paragraph(f'Shop {shop_id} Sales Report ({period_suffix})', title_style))
                elements.append(Spacer(1, 20))

                elements.append(Paragraph('Summary', styles['Heading2']))
                summary_data = [[k, f"{v:,.2f}" if isinstance(v, float) else f"{v:,}"] for k, v in summary.iloc[0].items()]
                from reportlab.platypus import Table
                from reportlab.platypus.tables import TableStyle
                summary_table = Table(summary_data)
                summary_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
                    ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                elements.append(summary_table)
                elements.append(Spacer(1, 20))

                data = [df.columns.values.tolist()] + df.values.tolist()
                detail_table = Table(data)
                detail_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FF5733')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                elements.append(detail_table)
                doc.build(elements)
                out.seek(0)
                return out.getvalue(), 'application/pdf', f'shop_{shop_id}_sales_{period_suffix}.pdf'
            else:
                raise ValueError(f"Unsupported format: {fmt}")
        except Exception as e:
            print(f"Shop analytics export error: {e}")
            return None, None, None
