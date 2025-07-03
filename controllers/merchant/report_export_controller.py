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
from controllers.merchant.report_controller import MerchantReportController

logger = logging.getLogger(__name__)


class MerchantReportExportController:
    """Controller for exporting merchant sales reports in various formats"""

    @staticmethod
    def export_sales_report(user_id, export_format='pdf'):
        """
        Export sales report in specified format (pdf, excel, csv)
        """
        try:
            # Get merchant profile
            merchant = MerchantProfile.get_by_user_id(user_id)
            if not merchant:
                raise Exception("Merchant profile not found")

            # Gather all report data
            report_data = MerchantReportExportController._gather_report_data(user_id, merchant)
            
            # Generate report based on format
            if export_format.lower() == 'pdf':
                return MerchantReportExportController._generate_pdf_report(report_data, merchant)
            elif export_format.lower() == 'excel':
                return MerchantReportExportController._generate_excel_report(report_data, merchant)
            elif export_format.lower() == 'csv':
                return MerchantReportExportController._generate_csv_report(report_data, merchant)
            else:
                raise Exception("Unsupported export format")

        except Exception as e:
            logger.error(f"Error exporting sales report: {str(e)}", exc_info=True)
            raise e

    @staticmethod
    def _gather_report_data(user_id, merchant):
        """Gather all necessary data for the sales report"""
        try:
            # Get monthly sales data (shown in monthly chart)
            monthly_sales = MerchantReportController.get_monthly_sales_analytics(user_id)
            
            # Get detailed sales data (shown in detailed table)
            detailed_sales = MerchantReportController.get_detailed_monthly_sales(user_id)
            
            # Get product performance (shown in bar chart)
            product_performance = MerchantReportController.get_product_performance(user_id)
            
            # Get revenue by category (shown in pie chart)
            category_revenue = MerchantReportController.get_revenue_by_category(user_id)
            
            return {
                'merchant_info': {
                    'business_name': merchant.business_name,
                    'merchant_id': merchant.id,
                    'email': merchant.business_email,
                    'phone': merchant.business_phone,
                    'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                },
                'monthly_sales': monthly_sales,
                'detailed_sales': detailed_sales,
                'product_performance': product_performance,
                'category_revenue': category_revenue
            }
            
        except Exception as e:
            logger.error(f"Error gathering report data: {str(e)}", exc_info=True)
            raise e

    @staticmethod
    def _generate_pdf_report(report_data, merchant):
        """Generate PDF report"""
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
            title = Paragraph(f"Sales Performance Report - {report_data['merchant_info']['business_name']}", title_style)
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
            
            # Monthly Sales
            if report_data['monthly_sales']:
                content.append(Paragraph("Monthly Sales Performance", heading_style))
                monthly_data = [['Month', 'Revenue', 'Units Sold']]
                for item in report_data['monthly_sales']:
                    monthly_data.append([item['month'], f"₹{item['revenue']:,.2f}", f"{item['units']:,}"])
                
                monthly_table = Table(monthly_data, colWidths=[2*inch, 2*inch, 1.5*inch])
                monthly_table.setStyle(TableStyle([
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
                content.append(monthly_table)
                content.append(Spacer(1, 20))
            
            # Product Performance
            if report_data['product_performance']:
                content.append(Paragraph("Product Performance", heading_style))
                products_data = [['Product Name', 'Revenue']]
                for item in report_data['product_performance']:
                    products_data.append([item['name'], f"₹{item['revenue']:,.2f}"])
                
                products_table = Table(products_data, colWidths=[3*inch, 2*inch])
                products_table.setStyle(TableStyle([
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
                content.append(products_table)
                content.append(Spacer(1, 20))
            
            # Category Revenue Distribution
            if report_data['category_revenue']:
                content.append(Paragraph("Revenue by Category", heading_style))
                category_data = [['Category', 'Percentage']]
                for item in report_data['category_revenue']:
                    category_data.append([item['name'], f"{item['value']}%"])
                
                category_table = Table(category_data, colWidths=[3*inch, 2*inch])
                category_table.setStyle(TableStyle([
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
                content.append(category_table)
            
            # Build PDF
            doc.build(content)
            pdf_data = buffer.getvalue()
            buffer.close()
            
            # Create response
            response = make_response(pdf_data)
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'attachment; filename=sales_report_{merchant.id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating PDF report: {str(e)}", exc_info=True)
            raise e

    @staticmethod
    def _generate_excel_report(report_data, merchant):
        """Generate Excel report"""
        try:
            # Create Excel buffer
            buffer = io.BytesIO()
            
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                # Merchant Info Sheet
                merchant_df = pd.DataFrame([report_data['merchant_info']])
                merchant_df.to_excel(writer, sheet_name='Merchant Info', index=False)
                
                # Monthly Sales Sheet
                if report_data['monthly_sales']:
                    monthly_df = pd.DataFrame(report_data['monthly_sales'])
                    monthly_df.to_excel(writer, sheet_name='Monthly Sales', index=False)
                
                # Detailed Sales Sheet
                if report_data['detailed_sales']:
                    detailed_df = pd.DataFrame(report_data['detailed_sales'])
                    detailed_df.to_excel(writer, sheet_name='Detailed Sales', index=False)
                
                # Product Performance Sheet
                if report_data['product_performance']:
                    products_df = pd.DataFrame(report_data['product_performance'])
                    products_df.to_excel(writer, sheet_name='Product Performance', index=False)
                
                # Category Revenue Sheet
                if report_data['category_revenue']:
                    category_df = pd.DataFrame(report_data['category_revenue'])
                    category_df.to_excel(writer, sheet_name='Category Revenue', index=False)
            
            excel_data = buffer.getvalue()
            buffer.close()
            
            # Create response
            response = make_response(excel_data)
            response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            response.headers['Content-Disposition'] = f'attachment; filename=sales_report_{merchant.id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating Excel report: {str(e)}", exc_info=True)
            raise e

    @staticmethod
    def _generate_csv_report(report_data, merchant):
        """Generate CSV report (combined data)"""
        try:
            # Create CSV buffer
            buffer = io.StringIO()
            
            # Write header
            buffer.write(f"Sales Performance Report - {report_data['merchant_info']['business_name']}\n")
            buffer.write(f"Generated: {report_data['merchant_info']['generated_at']}\n\n")
            
            # Monthly Sales
            if report_data['monthly_sales']:
                buffer.write("Monthly Sales\n")
                monthly_df = pd.DataFrame(report_data['monthly_sales'])
                monthly_df.to_csv(buffer, index=False)
                buffer.write("\n")
            
            # Product Performance
            if report_data['product_performance']:
                buffer.write("Product Performance\n")
                products_df = pd.DataFrame(report_data['product_performance'])
                products_df.to_csv(buffer, index=False)
                buffer.write("\n")
                
            # Category Revenue
            if report_data['category_revenue']:
                buffer.write("Revenue by Category\n")
                category_df = pd.DataFrame(report_data['category_revenue'])
                category_df.to_csv(buffer, index=False)
                buffer.write("\n")
            
            # Detailed Sales
            if report_data['detailed_sales']:
                buffer.write("Detailed Sales Data\n")
                detailed_df = pd.DataFrame(report_data['detailed_sales'])
                detailed_df.to_csv(buffer, index=False)
            
            csv_data = buffer.getvalue()
            buffer.close()
            
            # Create response
            response = make_response(csv_data)
            response.headers['Content-Type'] = 'text/csv'
            response.headers['Content-Disposition'] = f'attachment; filename=sales_report_{merchant.id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating CSV report: {str(e)}", exc_info=True)
            raise e
