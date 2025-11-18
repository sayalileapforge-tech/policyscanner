from __future__ import annotations
from pathlib import Path
import re
import hashlib
import pdfplumber
from typing import Dict, Any, List


def extract_full_text(pdf_path: Path) -> Dict[str, Any]:
    text_pages: List[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            txt = page.extract_text() or ""
            text_pages.append(txt)
    return {"pages": text_pages, "full_text": "\n".join(text_pages)}


def _re_get(pattern: str, text: str, flags=0, idx=1, default=None):
    m = re.search(pattern, text, flags)
    return m.group(idx).strip() if m else default


def parse_header_block(text: str) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    # Extract driver name - capture only until "Report Date" appears
    driver_name_match = re.search(r"DRIVER REPORT\s+(.+?)(?:\s+Report Date:|$)", text)
    data["driver_name"] = driver_name_match.group(1).strip() if driver_name_match else None
    dln = re.search(r"DLN:\s*([A-Z0-9\-]+)\s+([A-Za-z]+)", text)
    if dln:
        data["dln"] = dln.group(1).strip()
        data["province"] = dln.group(2).strip()
    data["date_of_birth"] = _re_get(r"Date of Birth:\s*([0-9\-]+)", text)
    data["report_date"] = _re_get(r"Report Date:\s*([0-9:\- ]+(?:EST|UTC|EDT|IST))", text)
    data["requestor"] = _re_get(r"Requestor:\s*(.+)", text)
    data["company"] = _re_get(r"Company:\s*(.+)", text)
    data["last_data_update"] = _re_get(r"Last Data Update:\s*([0-9\-]+)", text)
    data["years_of_data"] = _re_get(r"Number of Years of Data:\s*([0-9]+)", text)

    addr = _re_get(r"Address:\s*(.+?)\s+Number of Claims in Last 6 Years:", text, flags=re.DOTALL)
    if addr:
        data["address"] = " ".join(addr.split())

    for label, key in [
        ("Number of Claims in Last 6 Years", "num_claims_6y"),
        ("Number of At-Fault Claims in Last 6 Years", "num_atfault_6y"),
        ("Number of Comprehensive Losses in Last 6 Years", "num_comp_losses_6y"),
        ("Number of DCPD Claims in Last 6 Years", "num_dcpd_6y"),
    ]:
        v = _re_get(rf"{re.escape(label)}:\s*([0-9]+)", text)
        data[key] = int(v) if v else None

    data["gender"] = _re_get(r"Gender:\s*([A-Za-z]+)", text)
    data["marital_status"] = _re_get(r"Marital Status:\s*([A-Za-z]+)", text)
    v = _re_get(r"Years Licensed:\s*([0-9]+)", text)
    data["years_licensed"] = int(v) if v else None
    v = _re_get(r"Years of Continuous Insurance:\s*([0-9]+)", text)
    data["years_cont_insurance"] = int(v) if v else None
    v = _re_get(r"Years Claims Free:\s*([0-9]+)", text)
    data["years_claims_free"] = int(v) if v else None
    data["driver_training"] = _re_get(r"Driver Training:\s*([A-Za-z0-9]+)", text)
    return data


def split_policy_blocks(text: str) -> List[str]:
    parts = re.split(r"(Policy #\d+ .+)", text)
    policies: List[str] = []
    buf = None
    for part in parts:
        if part.startswith("Policy #"):
            if buf:
                policies.append(buf)
            buf = part
        else:
            if buf is not None:
                buf += part
    if buf:
        policies.append(buf)
    return policies


_STATUS_PAT = r"(Active|Inactive|Lapsed|Expired|Non-?Renewed(?:.*)?|Cancelled(?:.*)?)$"


def parse_policy_block(block: str) -> Dict[str, Any]:
    header: Dict[str, Any] = {
        "policy_number": _re_get(r"Policy #:?\s*([A-Z0-9]+)", block),
        "effective_date": _re_get(r"Effective Date:\s*([0-9\-]+)", block),
        "expiry_date": _re_get(r"Expiry Date:\s*([0-9\-]+)", block),
        "cancellation_date": _re_get(r"Cancellation Date:\s*([A-Za-z0-9\-\\/]+|N/A)", block),
        "policyholder_name": None,
        "policyholder_address": _re_get(r"Policyholder Address:\s*(.+)", block),
        "num_reported_operators": _re_get(r"Number of Reported Operators:\s*([0-9]+)", block),
        "num_pp_vehicles": _re_get(r"Number of Private Passenger Vehicles:\s*([0-9]+)", block),
        "policy_range": None,
        "insurer": None,
        "status": None,
        "range_insurer_status": None,
    }

    ph_name = (
        _re_get(r"Policyholder Name:\s*([^\n]+)", block) or
        _re_get(r"Policyholder:\s*([^\n]+)", block) or
        _re_get(r"Policy Holder Name:\s*([^\n]+)", block) or
        _re_get(r"Policy Holder:\s*([^\n]+)", block) or
        _re_get(r"Insured Name:\s*([^\n]+)", block) or
        _re_get(r"Insured:\s*([^\n]+)", block)
    )
    if ph_name:
        ph_name = re.sub(r"\s+(?:Expiry|Effective|Cancellation).*", "", ph_name).strip()
    header["policyholder_name"] = ph_name

    if not header.get("policy_number"):
        header["policy_number"] = (
            _re_get(r"Policy #\d+\s+([A-Z0-9\-]+)", block) or
            _re_get(r"Policy #\s*([A-Z0-9\-]+)", block) or
            _re_get(r"Policy Number:\s*([A-Z0-9\-]+)", block) or
            _re_get(r"Policy No\.?\s*:\s*([A-Z0-9\-]+)", block)
        )

    first = block.splitlines()[0].strip()
    rng = re.search(r"(\d{4}-\d{2}-\d{2}\s+to\s+\d{4}-\d{2}-\d{2})", first)
    if rng:
        header["policy_range"] = rng.group(1)

    m = re.match(rf"(Policy #\d+)\s+(\d{{4}}-\d{{2}}-\d{{2}}\s+to\s+\d{{4}}-\d{{2}}-\d{{2}})\s+(.+?)\s+{_STATUS_PAT}", first)
    if m:
        header["policy_range"] = header["policy_range"] or m.group(2).strip()
        header["insurer"] = m.group(3).strip()
        header["status"] = m.group(4).strip()
        header["range_insurer_status"] = first
    else:
        header["range_insurer_status"] = first
        if not header["policy_range"] and header["effective_date"] and header["expiry_date"]:
            header["policy_range"] = f"{header['effective_date']} to {header['expiry_date']}"

    ops_raw = re.split(r'(?m)^(?=Operator:)', block)
    operators: List[Dict[str, Any]] = []
    for i, op_block in enumerate(ops_raw):
        if not op_block.strip():
            continue

        # Truncate the operator block at the first Vehicle definition, if present.
        m_vehicle_def = re.search(r'(?m)^Vehicle #\d+:', op_block)
        if m_vehicle_def:
            op_content = op_block[:m_vehicle_def.start()]
        else:
            op_content = op_block

        # Operator name (may be missing)
        op_match = re.search(r'Operator:\s*([^\n]+)', op_block)
        op_name = None
        if op_match:
            op_name_raw = op_match.group(1).strip()
            op_name = re.sub(r'\s+Vehicle\s*#.*$', '', op_name_raw).strip()
            print(f"[DEBUG] Operator {i}: '{op_name}'")

        # Extract commonly needed operator fields from op_content
        dln_val = _re_get(r"DLN:\s*([A-Z0-9\-]+)", op_content)
        province_val = _re_get(r"DLN:\s*[A-Z0-9\-]+\s+([A-Za-z]+)", op_content)
        relationship_val = _re_get(r"Relationship to Policyholder:\s*([^\n]+)", op_content)
        year_of_birth_val = _re_get(r"Year of Birth:\s*([0-9]+)", op_content)

        # Terms - accept various date formats, extract only the date
        start_term_match = re.search(r"Start of the Earliest Term:\s*([0-9\-\/]+)", op_content)
        start_term_val = start_term_match.group(1).strip() if start_term_match else None
        
        end_term_match = re.search(r"End of the Latest Term:\s*([0-9\-\/]+)", op_content)
        end_term_val = end_term_match.group(1).strip() if end_term_match else None

        operators.append({
            "operator_name": op_name,
            "dln": dln_val,
            "province": province_val,
            "relationship": relationship_val,
            "year_of_birth": year_of_birth_val,
            "start_term": start_term_val,
            "end_term": end_term_val,
            "vehicle_ref": _re_get(r"(Vehicle #\d+: .+)", op_block),
        })

    # Extract vehicle blocks and build a minimal list with only vehicle, vin, coverage
    veh_raw = re.split(r"(Vehicle #\d+: .+)", block)
    vlist, curv = [], None
    for part in veh_raw:
        if part.startswith("Vehicle #"):
            if curv:
                vlist.append(curv)
            curv = {"raw": part}
        else:
            if curv:
                curv["raw"] += part
    if curv:
        vlist.append(curv)

    vehicles: List[Dict[str, Any]] = []
    simple_list: List[Dict[str, Any]] = []
    vin_re = re.compile(r"\b([A-HJ-NPR-Z0-9]{11,17})\b")
    for v in vlist:
        raw = v.get("raw", "")
        # ignore trailing operator blocks
        raw_trim = re.split(r"\bOperator:\b", raw, maxsplit=1)[0]

        # remainder after the Vehicle #X: label
        after_label = re.split(r"Vehicle #\d+:", raw_trim, maxsplit=1)
        remainder = after_label[1] if len(after_label) > 1 else raw_trim

        # year: first 4-digit year on the first line after label (required)
        first_line = remainder.splitlines()[0] if remainder.splitlines() else remainder
        year_m = re.search(r"((?:19|20)\d{2})", first_line)
        if not year_m:
            # skip blocks that don't contain a year (likely operator references)
            continue
        year = year_m.group(1)

        # vin (search in remainder)
        vin_m = vin_re.search(remainder)
        vin = vin_m.group(1).strip() if vin_m else None

        # coverage (may be after remainder or elsewhere in raw_trim)
        cov_m = re.search(r"Coverage:\s*([^\n\r]+)", raw_trim)
        coverage = cov_m.group(1).strip() if cov_m else None

        # make/model: text between year end (on the first line) and VIN (or between year and Coverage if VIN missing)
        make_model = None
        start_pos = year_m.end()
        end_pos = None
        # Look for VIN/coverage positions within the same first_line when possible
        if vin_m:
            # if VIN occurs in first_line, use that position; otherwise use position in remainder
            vin_pos = first_line.find(vin) if vin and vin in first_line else (remainder.find(vin) if vin else -1)
            if vin_pos != -1:
                end_pos = vin_pos
        if end_pos is None:
            cov_pos = first_line.find("Coverage:") if "Coverage:" in first_line else remainder.find("Coverage:")
            if cov_pos != -1:
                end_pos = cov_pos
        snippet = (first_line[start_pos:end_pos].strip() if end_pos is not None else first_line[start_pos:].strip()) if start_pos is not None else ""
        snippet = re.sub(r"^[:\-\s]+", "", snippet)
        snippet = re.sub(r"\bVIN:\b.*$", "", snippet, flags=re.IGNORECASE)
        # strip trailing punctuation/markers (hyphens, slashes, commas)
        snippet = re.sub(r"[\s\-/,:]+$", "", snippet)
        make_model = " ".join(snippet.split()) if snippet else None

        vehicle_label = f"{year} {make_model}" if (year and make_model) else (make_model or year)

        entry = {"vehicle": vehicle_label, "vin": vin, "coverage": coverage}
        vehicles.append(entry)
        simple_list.append(entry)
        print(f"[DEBUG VEHICLE] {raw.splitlines()[0] if raw else 'VEH'} -> vehicle={vehicle_label}, vin={vin}, coverage={coverage}")

    header["vehicles_simple"] = simple_list

    return {"header": header, "operators": operators, "vehicles": vehicles, "raw": block.strip()}


def parse_previous_inquiries(text: str) -> List[Dict[str, Any]]:
    m = re.search(r"Previous Inquiries(.+?)(?:Page \d+ of|\Z)", text, flags=re.DOTALL)
    if not m:
        return []
    lines = [l.strip() for l in m.group(1).splitlines() if l.strip()]
    out = []
    for line in lines:
        parts = re.split(r"\s{2,}", line, maxsplit=1)
        if len(parts) == 2 and re.match(r"\d{4}-\d{2}-\d{2}", parts[0]):
            out.append({"date": parts[0], "who": parts[1]})
    return out


def parse_claims(text: str) -> List[Dict[str, Any]]:
    # Split claim blocks by headings like 'Claim #1 ...'
    blocks = re.split(r"(Claim #\d+ .+)", text)
    claims, cur = [], None
    for part in blocks:
        if part.startswith("Claim #"):
            if cur:
                claims.append(cur)
            cur = part
        else:
            if cur:
                cur += part
    if cur:
        claims.append(cur)

    out: List[Dict[str, Any]] = []
    vin_re = re.compile(r"\b([A-HJ-NPR-Z0-9]{11,17})\b", flags=re.IGNORECASE)

    for cb in claims:
        # insurer: from line like 'Date of Loss 2023-07-12 Aviva Canada At-Fault'
        insurer = _re_get(r"Date of Loss\s+[0-9]{4}-[0-9]{2}-[0-9]{2}\s+(.+?)\s+At-?Fault", cb)
        # date_reported: 'Date Reported: YYYY-MM-DD'
        date_reported = _re_get(r"Date Reported\s*[:\s]*([0-9]{4}-[0-9]{2}-[0-9]{2})", cb)

        # vehicle: from 'Vehicle: 2008 HONDA ACCORD EX 4DR - VIN' (stop before VIN)
        vehicle = None
        m_vehicle = re.search(r"Vehicle\s*[:\s]*(?:((?:19|20)\d{2}\b[\s\S]*?))(?:\bVIN\b|\b[\-]\s*VIN\b|\b[\-]\s*[A-HJ-NPR-Z0-9]{11,17}\b|\n|$)", cb, flags=re.IGNORECASE)
        if m_vehicle:
            vtxt = m_vehicle.group(1).strip()
            # remove trailing separators and VIN-like tails
            vtxt = re.sub(r"[\-\s]*$", "", vtxt)
            # collapse whitespace
            vehicle = " ".join(vtxt.split())
        else:
            # fallback: try single-line match stopping at VIN
            m2 = re.search(r"Vehicle\s*[:\s]*([^\n]+?)\s*(?:VIN[:]?|$)", cb, flags=re.IGNORECASE)
            if m2:
                vehicle = m2.group(1).strip()

        # vin using strict VIN regex
        vin_m = vin_re.search(cb)
        vin = vin_m.group(1).upper() if vin_m else None

        # coverage and claim_status
        coverage = _re_get(r"Coverage\s*[:\s]*(.+?)(?:\n|$)", cb)
        claim_status = _re_get(r"Claim Status\s*[:\s]*(.+?)(?:\n|$)", cb)

        # at_fault: If 'At-Fault : 0%' -> False, else True if At-Fault present
        at_fault = False
        af_m = re.search(r"At[-\s]?Fault\s*[:\s]*([0-9]{1,3})%?", cb)
        if af_m:
            try:
                pct = int(af_m.group(1))
                at_fault = pct != 0
            except Exception:
                at_fault = True
        else:
            if re.search(r"\bAt[- ]?Fault\b", cb, flags=re.IGNORECASE):
                # present but no percent -> assume true
                at_fault = True

        # totals: extract numeric parts and normalize to plain numeric strings without $ or commas
        def _num_from(pattern, txt):
            m = re.search(pattern, txt, flags=re.IGNORECASE)
            if not m:
                return None
            s = m.group(1)
            s = s.replace(',', '').replace('$', '').strip()
            # ensure two-decimal formatting if possible
            try:
                f = float(s)
                return f"{f:.2f}"
            except Exception:
                return s

        total_loss = _num_from(r"Total Loss\s*[:\s]*\$?([0-9,]+(?:\.[0-9]{2})?)", cb)
        total_expense = _num_from(r"Total Expense\s*[:\s]*\$?([0-9,]+(?:\.[0-9]{2})?)", cb)

        # subtotal = total_loss + total_expense (numeric strings)
        try:
            tl_f = float(total_loss) if total_loss is not None else 0.0
        except Exception:
            tl_f = 0.0
        try:
            te_f = float(total_expense) if total_expense is not None else 0.0
        except Exception:
            te_f = 0.0
        subtotal = f"{(tl_f + te_f):.2f}"

        # Extract first and third party driver info from the claim block
        fp_name = None
        fp_license = None
        tp_name = None
        tp_license = None

        m_fp = re.search(r"First Party Driver(.+?)(?:Third Party Driver|$)", cb, flags=re.IGNORECASE | re.DOTALL)
        if m_fp:
            fp_block = m_fp.group(1)
            fp_name = _re_get(r"Name\s*:\s*(.+)", fp_block)
            fp_license = _re_get(r"License\s*:\s*(.+)", fp_block)

        m_tp = re.search(r"Third Party Driver(.+?)(?:$)", cb, flags=re.IGNORECASE | re.DOTALL)
        if m_tp:
            tp_block = m_tp.group(1)
            tp_name = _re_get(r"Name\s*:\s*(.+)", tp_block)
            tp_license = _re_get(r"License\s*:\s*(.+)", tp_block)

        out.append({
            "insurer": insurer,
            "vehicle": vehicle,
            "vin": vin,
            "date_reported": date_reported,
            "coverage": coverage,
            "claim_status": claim_status,
            "at_fault": bool(at_fault),
            "total_loss": total_loss,
            "total_expense": total_expense,
            "subtotal": subtotal,
            "first_party_driver": {"name": fp_name, "license": fp_license},
            "third_party_driver": {"name": tp_name, "license": tp_license},
        })

    return out


def parse_report(pdf_path: Path) -> Dict[str, Any]:
    extracted = extract_full_text(pdf_path)
    full_text = extracted["full_text"]
    header = parse_header_block(full_text)
    policies = [parse_policy_block(b) for b in split_policy_blocks(full_text)]
    inquiries = parse_previous_inquiries(full_text)
    claims = parse_claims(full_text)

    # Filter operators to only include those whose DLN matches the driver's DLN
    header_dln = header.get("dln")
    if header_dln:
        for policy in policies:
            if "operators" in policy:
                policy["operators"] = [
                    op for op in policy["operators"]
                    if op.get("dln") == header_dln
                ]

    sig_str = f"{pdf_path.name}|{header.get('driver_name')}|{header.get('report_date')}|{len(policies)}"
    doc_id = hashlib.sha1(sig_str.encode("utf-8")).hexdigest()

    return {
        "_id": doc_id,
        "file_name": pdf_path.name,
        "header": header,
        "policies": policies,
        "previous_inquiries": inquiries,
        "claims": claims,
        "pages_count": len(extracted["pages"]),
        "extraction_stats": [len(p) for p in extracted["pages"]],
        "full_text": full_text,
    }
