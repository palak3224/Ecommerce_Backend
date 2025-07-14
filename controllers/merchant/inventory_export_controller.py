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
            doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=50, leftMargin=50,
                                  topMargin=50, bottomMargin=50)
            
            # Get styles
            styles = getSampleStyleSheet()
            
            # Create custom styles
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=20,
                spaceAfter=30,
                alignment=TA_CENTER,
                textColor=colors.HexColor('#FF4D00'),
                fontName='Helvetica-Bold'
            )
            
            subtitle_style = ParagraphStyle(
                'CustomSubtitle',
                parent=styles['Normal'],
                fontSize=12,
                spaceAfter=20,
                alignment=TA_CENTER,
                textColor=colors.HexColor('#666666'),
                fontName='Helvetica'
            )
            
            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=16,
                spaceAfter=15,
                spaceBefore=25,
                textColor=colors.HexColor('#333333'),
                fontName='Helvetica-Bold'
            )
            
            section_style = ParagraphStyle(
                'SectionStyle',
                parent=styles['Normal'],
                fontSize=10,
                spaceAfter=8,
                textColor=colors.HexColor('#333333'),
                fontName='Helvetica'
            )
            
            # Build PDF content
            content = []
            
            # Title
            title = Paragraph(f"Inventory Report", title_style)
            content.append(title)
            
            # Subtitle
            subtitle = Paragraph(f"{report_data['merchant_info']['business_name']}", subtitle_style)
            content.append(subtitle)
            
            # Report Info
            report_info = [
                ['Report Generated:', report_data['merchant_info']['generated_at']],
                ['Merchant ID:', str(report_data['merchant_info']['merchant_id'])],
                ['Business Email:', report_data['merchant_info']['email']],
                ['Business Phone:', report_data['merchant_info']['phone'] or 'N/A']
            ]
            
            report_table = Table(report_info, colWidths=[2.5*inch, 3.5*inch])
            report_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F8F9FA')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E0E0E0')),
                ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#FAFAFA')])
            ]))
            content.append(report_table)
            content.append(Spacer(1, 25))
            
            # Inventory Statistics
            if report_data['inventory_stats']:
                content.append(Paragraph("Inventory Overview", heading_style))
                
                stats = report_data['inventory_stats']
                stats_data = [
                    ['Metric', 'Value'],
                    ['Total Products', f"{stats.get('total_products', 0):,}"],
                    ['Total Stock Quantity', f"{stats.get('total_stock', 0):,}"],
                    ['Low Stock Products', f"{stats.get('low_stock_count', 0):,}"],
                    ['Out of Stock Products', f"{stats.get('out_of_stock_count', 0):,}"]
                  
                ]
                
                stats_table = Table(stats_data, colWidths=[2.5*inch, 2*inch])
                stats_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FF4D00')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 11),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                    ('TOPPADDING', (0, 0), (-1, 0), 10),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8F9FA')),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 10),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E0E0E0')),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FAFAFA')])
                ]))
                content.append(stats_table)
                content.append(Spacer(1, 25))
            
            # Products Table
            if report_data['products']:
                content.append(Paragraph("Product Inventory Details", heading_style))
                
                # Create a function to truncate text
                def truncate_text(text, max_length=30):
                    if len(text) <= max_length:
                        return text
                    return text[:max_length-3] + "..."
                
                # Prepare products data with proper text handling
                products_data = [['Product Name', 'SKU', 'Category', 'Brand', 'Stock Qty', 'Available', 'Status']]
                
                # Limit to first 100 products for PDF readability
                limited_products = report_data['products'][:100]
                for product in limited_products:
                    products_data.append([
                        truncate_text(product['name'], 25),
                        truncate_text(product['sku'], 12),
                        truncate_text(product['category'], 15),
                        truncate_text(product['brand'], 15),
                        str(product['stock_qty']),
                        str(product['available']),
                        product['stock_status']
                    ])
                
                # Add note if there are more products
                if len(report_data['products']) > 100:
                    note = f"Note: Showing first 100 products out of {len(report_data['products'])} total products. Download Excel/CSV for complete data."
                    content.append(Paragraph(note, section_style))
                    content.append(Spacer(1, 10))
                
                # Calculate column widths to fit the page
                products_table = Table(products_data, colWidths=[1.8*inch, 0.8*inch, 0.9*inch, 0.9*inch, 0.6*inch, 0.6*inch, 0.8*inch])
                products_table.setStyle(TableStyle([
                    # Header styling
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FF4D00')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                    ('TOPPADDING', (0, 0), (-1, 0), 8),
                    
                    # Data rows styling
                    ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
                    ('ALIGN', (0, 1), (0, -1), 'LEFT'),  # Product name left-aligned
                    ('ALIGN', (1, 1), (1, -1), 'LEFT'),   # SKU left-aligned
                    ('ALIGN', (2, 1), (2, -1), 'LEFT'),   # Category left-aligned
                    ('ALIGN', (3, 1), (3, -1), 'LEFT'),   # Brand left-aligned
                    
                    # Grid and spacing
                    ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#E0E0E0')),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FAFAFA')]),
                    ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
                    ('TOPPADDING', (0, 1), (-1, -1), 4),
                    
                    # Status column color coding
                    ('BACKGROUND', (6, 1), (6, -1), colors.HexColor('#F8F9FA')),
                ]))
                
                content.append(products_table)
                content.append(Spacer(1, 20))
                
                # Add summary statistics
                if limited_products:
                    content.append(Paragraph("Summary by Stock Status", heading_style))
                    
                    # Calculate summary
                    status_counts = {}
                    for product in limited_products:
                        status = product['stock_status']
                        status_counts[status] = status_counts.get(status, 0) + 1
                    
                    summary_data = [['Stock Status', 'Product Count']]
                    for status, count in status_counts.items():
                        summary_data.append([status, str(count)])
                    
                    summary_table = Table(summary_data, colWidths=[2.5*inch, 2*inch])
                    summary_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FF4D00')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 10),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8F9FA')),
                        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 1), (-1, -1), 10),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E0E0E0')),
                    ]))
                    content.append(summary_table)
            
            # Footer
            content.append(Spacer(1, 30))
            footer_style = ParagraphStyle(
                'FooterStyle',
                parent=styles['Normal'],
                fontSize=8,
                alignment=TA_CENTER,
                textColor=colors.HexColor('#999999'),
                fontName='Helvetica'
            )
            footer = Paragraph(f"This report was generated on {report_data['merchant_info']['generated_at']} for {report_data['merchant_info']['business_name']}", footer_style)
            content.append(footer)
            
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
