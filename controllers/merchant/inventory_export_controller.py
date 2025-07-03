import pandas as pd
import json
import io
from datetime import datetime, date
from decimal import Decimal
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from flask import make_response
import logging
from auth.models.models import MerchantProfile
from controllers.merchant.product_stock_controller import MerchantProductStockController

logger = logging.getLogger(__name__)


class MerchantInventoryExportController:
    """Controller for exporting merchant inventory reports in various formats"""

    @staticmethod
    def export_inventory_report(user_id, export_format='pdf', filters=None):
        """
        Export inventory report in specified format (pdf, excel, csv)
        """
        try:
            # Get merchant profile
            merchant = MerchantProfile.get_by_user_id(user_id)
            if not merchant:
                raise Exception("Merchant profile not found")

            # Gather all inventory data
            report_data = MerchantInventoryExportController._gather_inventory_data(user_id, merchant, filters)
            
            # Generate report based on format
            if export_format.lower() == 'pdf':
                return MerchantInventoryExportController._generate_pdf_report(report_data, merchant)
            elif export_format.lower() == 'excel':
                return MerchantInventoryExportController._generate_excel_report(report_data, merchant)
            elif export_format.lower() == 'csv':
                return MerchantInventoryExportController._generate_csv_report(report_data, merchant)
            else:
                raise Exception("Unsupported export format")

        except Exception as e:
            logger.error(f"Error exporting inventory report: {str(e)}", exc_info=True)
            raise e

    @staticmethod
    def _gather_inventory_data(user_id, merchant, filters=None):
        """Gather all necessary inventory data shown on the inventory page"""
        try:
            # Get inventory statistics
            inventory_stats = MerchantProductStockController.get_inventory_stats(user_id)
            
            # Get products list with the same filters as the inventory page
            products_data = MerchantInventoryExportController._get_all_products(user_id, filters)
            
            return {
                'merchant_info': {
                    'business_name': merchant.business_name,
                    'merchant_id': merchant.id,
                    'email': merchant.business_email,
                    'phone': merchant.business_phone,
                    'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                },
                'inventory_stats': inventory_stats,
                'products': products_data
            }
            
        except Exception as e:
            logger.error(f"Error gathering inventory data: {str(e)}", exc_info=True)
            raise e

    @staticmethod
    def _get_all_products(user_id, filters=None):
        """Get all products for export (without pagination)"""
        try:
            # Use the existing product stock controller to get all products
            # We'll get products in batches to avoid memory issues
            all_products = []
            page = 1
            per_page = 100
            
            while True:
                products_response = MerchantProductStockController.get_products(
                    user_id=user_id,
                    page=page,
                    per_page=per_page,
                    search=filters.get('search') if filters else None,
                    category=filters.get('category') if filters else None,
                    brand=filters.get('brand') if filters else None,
                    stock_status=filters.get('stock_status') if filters else None
                )
                
                if not products_response or not products_response.get('products'):
                    break
                    
                products = products_response['products']
                
                # Transform product data for export
                for product in products:
                    stock_status = "Out of Stock"
                    if product['stock_qty'] > product['low_stock_threshold']:
                        stock_status = "In Stock"
                    elif product['stock_qty'] > 0:
                        stock_status = "Low Stock"
                    
                    all_products.append({
                        'id': product['id'],
                        'name': product['name'],
                        'sku': product['sku'],
                        'category': product['category']['name'] if product.get('category') else 'N/A',
                        'brand': product['brand']['name'] if product.get('brand') else 'N/A',
                        'stock_qty': product['stock_qty'],
                        'available': product['available'],
                        'low_stock_threshold': product['low_stock_threshold'],
                        'stock_status': stock_status
                    })
                
                # Check if we have more pages
                pagination = products_response.get('pagination', {})
                if page >= pagination.get('total_pages', 1):
                    break
                    
                page += 1
            
            return all_products
            
        except Exception as e:
            logger.error(f"Error getting all products: {str(e)}", exc_info=True)
            raise e

    @staticmethod
    def _generate_pdf_report(report_data, merchant):
        """Generate PDF inventory report"""
        try:
            # Create PDF buffer
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72,
                                  topMargin=72, bottomMargin=18)
            
            # Get styles
            styles = getSampleStyleSheet()
            
            # Create custom styles
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                spaceAfter=30,
                alignment=TA_CENTER,
                textColor=colors.HexColor('#FF4D00')
            )
            
            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=14,
                spaceAfter=12,
                spaceBefore=20,
                textColor=colors.HexColor('#333333')
            )
            
            # Build PDF content
            content = []
            
            # Title
            title = Paragraph(f"Inventory Report - {report_data['merchant_info']['business_name']}", title_style)
            content.append(title)
            content.append(Spacer(1, 20))
            
            # Merchant Info
            merchant_info = [
                ['Business Name:', report_data['merchant_info']['business_name']],
                ['Merchant ID:', str(report_data['merchant_info']['merchant_id'])],
                ['Email:', report_data['merchant_info']['email']],
                ['Phone:', report_data['merchant_info']['phone']],
                ['Generated:', report_data['merchant_info']['generated_at']]
            ]
            
            merchant_table = Table(merchant_info, colWidths=[2*inch, 3*inch])
            merchant_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F8F9FA')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            content.append(merchant_table)
            content.append(Spacer(1, 20))
            
            # Inventory Statistics
            if report_data['inventory_stats']:
                content.append(Paragraph("Inventory Statistics", heading_style))
                stats = report_data['inventory_stats']
                stats_data = [
                    ['Metric', 'Value'],
                    ['Total Products', f"{stats.get('total_products', 0):,}"],
                    ['Total Stock Quantity', f"{stats.get('total_stock', 0):,}"],
                    ['Low Stock Products', f"{stats.get('low_stock_count', 0):,}"],
                    ['Out of Stock Products', f"{stats.get('out_of_stock_count', 0):,}"],
                    ['Inventory Value', f"${stats.get('inventory_value', 0):,.2f}"]
                ]
                
                stats_table = Table(stats_data, colWidths=[2.5*inch, 2*inch])
                stats_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FF4D00')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 12),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 10),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                content.append(stats_table)
                content.append(Spacer(1, 20))
            
            # Products Table (first 50 products to avoid huge PDFs)
            if report_data['products']:
                content.append(Paragraph("Product Inventory", heading_style))
                products_data = [['Product Name', 'SKU', 'Category', 'Brand', 'Stock', 'Available', 'Status']]
                
                # Limit to first 50 products for PDF readability
                limited_products = report_data['products'][:50]
                for product in limited_products:
                    products_data.append([
                        product['name'][:25] + ('...' if len(product['name']) > 25 else ''),
                        product['sku'],
                        product['category'][:15] + ('...' if len(product['category']) > 15 else ''),
                        product['brand'][:15] + ('...' if len(product['brand']) > 15 else ''),
                        str(product['stock_qty']),
                        str(product['available']),
                        product['stock_status']
                    ])
                
                # Add note if there are more products
                if len(report_data['products']) > 50:
                    note = f"Note: Showing first 50 products out of {len(report_data['products'])} total products. Download Excel/CSV for complete data."
                    content.append(Paragraph(note, styles['Normal']))
                    content.append(Spacer(1, 10))
                
                products_table = Table(products_data, colWidths=[1.5*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.5*inch, 0.6*inch, 0.7*inch])
                products_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FF4D00')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 7),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
                ]))
                content.append(products_table)
            
            # Build PDF
            doc.build(content)
            pdf_data = buffer.getvalue()
            buffer.close()
            
            # Create response
            response = make_response(pdf_data)
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'attachment; filename=inventory_report_{merchant.id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating PDF inventory report: {str(e)}", exc_info=True)
            raise e

    @staticmethod
    def _generate_excel_report(report_data, merchant):
        """Generate Excel inventory report"""
        try:
            # Create Excel buffer
            buffer = io.BytesIO()
            
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                # Merchant Info Sheet
                merchant_df = pd.DataFrame([report_data['merchant_info']])
                merchant_df.to_excel(writer, sheet_name='Merchant Info', index=False)
                
                # Inventory Statistics Sheet
                if report_data['inventory_stats']:
                    stats_df = pd.DataFrame([report_data['inventory_stats']])
                    stats_df.to_excel(writer, sheet_name='Inventory Statistics', index=False)
                
                # Products Sheet
                if report_data['products']:
                    products_df = pd.DataFrame(report_data['products'])
                    products_df.to_excel(writer, sheet_name='Product Inventory', index=False)
                
                # Summary by Category Sheet
                if report_data['products']:
                    category_summary = pd.DataFrame(report_data['products']).groupby('category').agg({
                        'stock_qty': 'sum',
                        'available': 'sum',
                        'id': 'count'
                    }).rename(columns={'id': 'product_count'}).reset_index()
                    category_summary.to_excel(writer, sheet_name='Category Summary', index=False)
                
                # Summary by Stock Status Sheet
                if report_data['products']:
                    status_summary = pd.DataFrame(report_data['products']).groupby('stock_status').agg({
                        'stock_qty': 'sum',
                        'available': 'sum',
                        'id': 'count'
                    }).rename(columns={'id': 'product_count'}).reset_index()
                    status_summary.to_excel(writer, sheet_name='Stock Status Summary', index=False)
            
            excel_data = buffer.getvalue()
            buffer.close()
            
            # Create response
            response = make_response(excel_data)
            response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            response.headers['Content-Disposition'] = f'attachment; filename=inventory_report_{merchant.id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating Excel inventory report: {str(e)}", exc_info=True)
            raise e

    @staticmethod
    def _generate_csv_report(report_data, merchant):
        """Generate CSV inventory report (combined data)"""
        try:
            # Create CSV buffer
            buffer = io.StringIO()
            
            # Write header
            buffer.write(f"Inventory Report - {report_data['merchant_info']['business_name']}\n")
            buffer.write(f"Generated: {report_data['merchant_info']['generated_at']}\n\n")
            
            # Inventory Statistics
            if report_data['inventory_stats']:
                buffer.write("Inventory Statistics\n")
                stats_df = pd.DataFrame([report_data['inventory_stats']])
                stats_df.to_csv(buffer, index=False)
                buffer.write("\n")
            
            # Products Inventory
            if report_data['products']:
                buffer.write("Product Inventory\n")
                products_df = pd.DataFrame(report_data['products'])
                products_df.to_csv(buffer, index=False)
                buffer.write("\n")
            
            csv_data = buffer.getvalue()
            buffer.close()
            
            # Create response
            response = make_response(csv_data)
            response.headers['Content-Type'] = 'text/csv'
            response.headers['Content-Disposition'] = f'attachment; filename=inventory_report_{merchant.id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating CSV inventory report: {str(e)}", exc_info=True)
            raise e
