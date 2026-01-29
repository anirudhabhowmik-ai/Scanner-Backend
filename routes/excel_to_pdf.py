from flask import Blueprint, request, send_file, jsonify
from io import BytesIO
import pandas as pd
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer, Paragraph
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet

excel_to_pdf_bp = Blueprint("excel_to_pdf", __name__)

@excel_to_pdf_bp.route("/excel-to-pdf", methods=["POST"])
def excel_to_pdf():
    try:
        if "files" not in request.files:
            return jsonify({"error": "No files uploaded"}), 400

        files = request.files.getlist("files")

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
        elements = []
        styles = getSampleStyleSheet()

        for file in files:
            excel_file = pd.ExcelFile(file)

            for sheet_name in excel_file.sheet_names:
                df = excel_file.parse(sheet_name, header=None)

                # Remove fully empty rows & columns
                df = df.dropna(how='all')
                df = df.dropna(axis=1, how='all')

                # Replace NaN with blank
                df = df.fillna("")

                # Remove "Unnamed" style columns
                df = df.loc[:, ~df.iloc[0].astype(str).str.contains("Unnamed", case=False)]

                if df.empty:
                    continue

                # Sheet title
                elements.append(Paragraph(f"{file.filename} - {sheet_name}", styles["Heading3"]))
                elements.append(Spacer(1, 10))

                data = df.values.tolist()

                # Auto column widths
                col_widths = [max(len(str(cell)) for cell in col) * 5 for col in zip(*data)]

                table = Table(data, colWidths=col_widths)
                table.setStyle(TableStyle([
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                ]))

                elements.append(table)
                elements.append(Spacer(1, 20))

        doc.build(elements)
        buffer.seek(0)

        return send_file(
            buffer,
            as_attachment=True,
            download_name="excel_converted.pdf",
            mimetype="application/pdf"
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500
