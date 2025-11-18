# backend/main.py
from __future__ import annotations
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
import tempfile

try:
    # Prefer the fixed parser when available; fall back to minimal stub while debugging.
    from .parser import parse_report  # type: ignore
except Exception:
    from .parser_minimal import parse_report  # type: ignore
from .db import upsert_report, list_reports, get_report, delete_report, clear_mock_store

app = FastAPI(title="DASH PDF Parser")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# ✅ Serve static assets at /static
static_dir = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ✅ Serve index at /
@app.get("/")
def root_index():
    index_file = Path(__file__).parent.parent / "static" / "index.html"
    return FileResponse(str(index_file))

class DiffRequest(BaseModel):
    policyA: dict
    policyB: dict

def dict_diff(a: dict, b: dict, path=""):
    diffs = []

    def is_scalar(x):
        return isinstance(x, (str, int, float, type(None), bool))

    keys = set(a.keys()) | set(b.keys())
    for k in sorted(keys):
        av = a.get(k)
        bv = b.get(k)
        p = f"{path}.{k}" if path else k

        if isinstance(av, list) and isinstance(bv, list):
            maxlen = max(len(av), len(bv))
            for i in range(maxlen):
                ai = av[i] if i < len(av) else None
                bi = bv[i] if i < len(bv) else None
                if isinstance(ai, dict) and isinstance(bi, dict):
                    diffs.extend(dict_diff(ai, bi, f"{p}[{i}]"))
                elif ai != bi:
                    diffs.append({"path": f"{p}[{i}]", "A": ai, "B": bi})
            continue

        if isinstance(av, dict) and isinstance(bv, dict):
            diffs.extend(dict_diff(av, bv, p))
        else:
            if av != bv and (is_scalar(av) or is_scalar(bv) or av is None or bv is None):
                diffs.append({"path": p, "A": av, "B": bv})

    return diffs

@app.post("/api/parse")
async def parse_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    report = parse_report(tmp_path)
    upserted = upsert_report(report)
    tmp_path.unlink(missing_ok=True)
    return {"ok": True, "report": upserted}

@app.get("/api/reports")
def api_list_reports():
    items = list_reports()
    return {"ok": True, "reports": items}

@app.get("/api/reports/{doc_id}")
def api_get_report(doc_id: str):
    doc = get_report(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True, "report": doc}

@app.delete("/api/reports/{doc_id}")
def api_delete_report(doc_id: str):
    """Delete a report by ID."""
    deleted = delete_report(doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"ok": True, "message": "Report deleted"}

@app.post("/api/clear")
def api_clear_data():
    """Clear all cached reports - for development only."""
    clear_mock_store()
    return {"ok": True, "message": "All data cleared"}

@app.post("/api/diff")
def api_diff(req: DiffRequest):
    diffs = dict_diff(req.policyA, req.policyB)
    return {"ok": True, "diff": diffs}

@app.get("/api/export/{doc_id}")
def api_export_pdf(doc_id: str):
    """Export report as PDF with all information."""
    doc = get_report(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Report not found")
    
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from pathlib import Path
    
    # Create temporary PDF file
    tmp_pdf = Path(tempfile.gettempdir()) / f"report_{doc_id}.pdf"
    
    try:
        doc_pdf = SimpleDocTemplate(str(tmp_pdf), pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#6d5dfc'),
            spaceAfter=10,
            alignment=1  # Center
        )
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#111827'),
            spaceAfter=6,
            spaceBefore=6
        )
        
        story = []
        
        # Title
        story.append(Paragraph("DASH Insurance Report", title_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Section 1: Driver Information
        header = doc.get("header", {})
        story.append(Paragraph("Driver Information", heading_style))
        
        driver_data = [
            ["Driver Name", str(header.get("driver_name", "—"))],
            ["Address", str(header.get("address", "—"))],
            ["DLN", f"{header.get('dln', '—')} {header.get('province', '')}".strip()],
            ["Date of Birth", str(header.get("date_of_birth", "—"))],
            ["Gender", str(header.get("gender", "—"))],
            ["Marital Status", str(header.get("marital_status", "—"))],
            ["Claims (6y)", str(header.get("num_claims_6y", "—"))],
            ["At-Fault Claims (6y)", str(header.get("num_atfault_6y", "—"))],
            ["Years Continuous Insurance", str(header.get("years_cont_insurance", "—"))],
        ]
        driver_table = Table(driver_data, colWidths=[2*inch, 4*inch])
        driver_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0edff')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e6e8ef')),
        ]))
        story.append(driver_table)
        story.append(Spacer(1, 0.2*inch))
        
        # Section 2: Policies
        policies = doc.get("policies", [])
        if policies:
            story.append(Paragraph("Policies", heading_style))
            for idx, policy in enumerate(reversed(policies)):
                ph = policy.get("header", {})
                ops = policy.get("operators", [])
                
                policy_data = [
                    ["Policy #", str(ph.get("policy_number", "—"))],
                    ["Company", str(ph.get("insurer", ph.get("range_insurer_status", "—")))],
                    ["Effective Date", str(ph.get("effective_date", "—"))],
                    ["Expiry Date", str(ph.get("expiry_date", "—"))],
                    ["Status", str(ph.get("status", "—"))],
                    ["Operators", str(len(ops))],
                ]
                policy_table = Table(policy_data, colWidths=[2*inch, 4*inch])
                policy_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#faf0ff')),
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e6e8ef')),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                ]))
                story.append(policy_table)
                story.append(Spacer(1, 0.1*inch))
            story.append(Spacer(1, 0.2*inch))
        
        # Section 3: Claims
        claims = doc.get("claims", [])
        if claims:
            story.append(Paragraph("Claims", heading_style))
            claims_data = [["Claim #", "Date", "Insurer", "At-Fault", "Status"]]
            for idx, claim in enumerate(claims):
                claims_data.append([
                    f"#{idx+1}",
                    str(claim.get("date_of_loss", "—")),
                    str(claim.get("insurer", "—")),
                    str(claim.get("at_fault", "—")),
                    str(claim.get("claim_status", "—")),
                ])
            claims_table = Table(claims_data, colWidths=[0.8*inch, 1.2*inch, 1.8*inch, 0.8*inch, 1.2*inch])
            claims_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0edff')),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e6e8ef')),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fafbff')]),
            ]))
            story.append(claims_table)
            story.append(Spacer(1, 0.2*inch))
        
        # Section 4: Previous Inquiries
        inquiries = doc.get("previous_inquiries", [])
        if inquiries:
            story.append(Paragraph("Previous Inquiries", heading_style))
            inq_data = [["Date", "Who"]]
            for inq in inquiries:
                inq_data.append([
                    str(inq.get("date", "—")),
                    str(inq.get("who", "—")),
                ])
            inq_table = Table(inq_data, colWidths=[2*inch, 4*inch])
            inq_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0edff')),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e6e8ef')),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
            ]))
            story.append(inq_table)
        
        # Build PDF
        doc_pdf.build(story)
        
        # Return file
        filename = f"report_{doc_id[:8]}.pdf"
        return FileResponse(
            str(tmp_pdf),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")
