from __future__ import annotations
from pathlib import Path
import re
import hashlib
import pdfplumber
from typing import Dict, Any, List
from datetime import datetime


def format_date_to_mmddyyyy(date_str: str) -> str:
    """Convert various date formats to MM/DD/YYYY format."""
    if not date_str or date_str == "N/A" or date_str == "—":
        return date_str
    
    # Remove timezone info if present (e.g., "2025-11-07 19-43-39-EST")
    date_str = re.sub(r'\s*(?:EST|UTC|EDT|IST|GMT|CST|PST|MST|AST|NST).*$', '', date_str.strip())
    
    # Try parsing YYYY-MM-DD format (most common)
    try:
        if re.match(r'^\d{4}-\d{2}-\d{2}', date_str):
            dt = datetime.strptime(date_str[:10], '%Y-%m-%d')
            return dt.strftime('%m/%d/%Y')
    except (ValueError, TypeError):
        pass
    
    # Try parsing MM-DD-YYYY or MM/DD/YYYY (already correct or similar)
    try:
        if re.match(r'^\d{1,2}[-/]\d{1,2}[-/]\d{4}', date_str):
            # Normalize to MM/DD/YYYY
            dt = datetime.strptime(date_str[:10], '%m-%d-%Y') if '-' in date_str[:10] else datetime.strptime(date_str[:10], '%m/%d/%Y')
            return dt.strftime('%m/%d/%Y')
    except (ValueError, TypeError):
        pass
    
    # Return original if conversion fails
    return date_str


def extract_policy_date(block: str, date_type: str = "effective") -> str:
    """
    Extract policy effective or expiry date while ignoring print/generated dates.
    
    Args:
        block: Policy block text
        date_type: "effective" for start date, "expiry" for end date
    
    Returns:
        Formatted date string in MM/DD/YYYY format, or empty string if not found
    """
    # Keywords that indicate the date we're looking for
    if date_type == "effective":
        target_keywords = [r"Start(?:\s+of\s+the\s+Earliest)?", r"Effective", r"Issue", r"Beginning", r"Policy\s+Start", r"Period\s+From"]
    else:  # expiry
        target_keywords = [r"End(?:\s+of\s+the\s+Latest)?", r"Expiry", r"Expiration", r"Period\s+To"]
    
    # Keywords to ignore (print/generated dates)
    ignore_keywords = [r"Print", r"Generated", r"Revised", r"Billed", r"Printed", r"Report\s+Date"]
    
    # Split into lines and process from top (header) to bottom
    lines = block.split('\n')
    
    for line in lines[:30]:  # Only check first 30 lines (near header)
        line_lower = line.lower()
        
        # Skip lines with ignore keywords
        if any(re.search(keyword, line_lower, re.IGNORECASE) for keyword in ignore_keywords):
            continue
        
        # Check if line contains target keyword
        has_target = any(re.search(keyword, line_lower, re.IGNORECASE) for keyword in target_keywords)
        
        if has_target:
            # Extract date from this line (YYYY-MM-DD or MM/DD/YYYY or MM-DD-YYYY)
            date_match = re.search(r'(\d{4}-\d{2}-\d{2}|\d{1,2}[-/]\d{1,2}[-/]\d{4})', line)
            if date_match:
                return format_date_to_mmddyyyy(date_match.group(1))
    
    return ""


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
    data["date_of_birth"] = format_date_to_mmddyyyy(_re_get(r"Date of Birth:\s*([0-9\-]+)", text) or "")
    data["report_date"] = format_date_to_mmddyyyy(_re_get(r"Report Date:\s*([0-9:\- ]+(?:EST|UTC|EDT|IST))", text) or "")
    data["requestor"] = _re_get(r"Requestor:\s*(.+)", text)
    data["company"] = _re_get(r"Company:\s*(.+)", text)
    data["last_data_update"] = format_date_to_mmddyyyy(_re_get(r"Last Data Update:\s*([0-9\-]+)", text) or "")
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
        "effective_date": extract_policy_date(block, "effective"),
        "expiry_date": extract_policy_date(block, "expiry"),
        "cancellation_date": format_date_to_mmddyyyy(_re_get(r"Cancellation Date:\s*([A-Za-z0-9\-\\/]+|N/A)", block) or ""),
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
            out.append({"date": format_date_to_mmddyyyy(parts[0]), "who": parts[1]})
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
        # date_of_loss and insurer: from line like 'Date of Loss 2023-07-12 Aviva Canada At-Fault'
        date_of_loss_raw = _re_get(r"Date of Loss\s+([0-9]{4}-[0-9]{2}-[0-9]{2})", cb)
        date_of_loss = format_date_to_mmddyyyy(date_of_loss_raw or "")
        insurer = _re_get(r"Date of Loss\s+[0-9]{4}-[0-9]{2}-[0-9]{2}\s+(.+?)\s+At-?Fault", cb)
        # date_reported: 'Date Reported: YYYY-MM-DD'
        date_reported_raw = _re_get(r"Date Reported\s*[:\s]*([0-9]{4}-[0-9]{2}-[0-9]{2})", cb)
        date_reported = format_date_to_mmddyyyy(date_reported_raw or "")

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

        # Extract kind_of_loss (KOL) entries - pattern like "KOL26 - Glass/windshield damage not caused by windstorm or hail: $1,057.00 (Loss); $0.00 (Expense)"
        kind_of_loss_list = []
        kol_pattern = r"(KOL\d+)\s*[-–]\s*([^:]+):\s*\$([0-9,]+(?:\.[0-9]{2})?)\s*\(Loss\);\s*\$([0-9,]+(?:\.[0-9]{2})?)\s*\(Expense\)"
        for kol_match in re.finditer(kol_pattern, cb, flags=re.IGNORECASE):
            kol_code = kol_match.group(1).strip()
            kol_description = kol_match.group(2).strip()
            kol_loss = kol_match.group(3).replace(',', '').replace('$', '').strip()
            kol_expense = kol_match.group(4).replace(',', '').replace('$', '').strip()
            kind_of_loss_list.append({
                "code": kol_code,
                "description": kol_description,
                "loss": kol_loss,
                "expense": kol_expense
            })

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
            "date_of_loss": date_of_loss,
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
            "kind_of_loss": kind_of_loss_list,
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

    header_dln = header.get("dln")
    
    # STEP 1: Build a mapping of each DLN to its operators in CHRONOLOGICAL order
    # Only include operators where operator.dln == header_dln (all must be same DLN)
    dln_policies: Dict[str, List[tuple]] = {}  # Maps DLN -> [(policy_idx, operator)]
    
    for policy_idx, policy in enumerate(policies):
        if "operators" not in policy or len(policy["operators"]) == 0:
            continue
        
        for operator in policy["operators"]:
            op_dln = operator.get("dln")
            if not op_dln:
                continue
            
            # CRITICAL: Only process operators where DLN matches header_dln
            if header_dln and op_dln != header_dln:
                print(f"[DEBUG] IGNORING operator with DLN {op_dln} (header_dln={header_dln})")
                continue
            
            if op_dln not in dln_policies:
                dln_policies[op_dln] = []
            
            # Store (policy_idx, operator) in CHRONOLOGICAL order
            dln_policies[op_dln].append((policy_idx, operator))
    
    # STEP 2 & 3: Apply shifting ONLY within each DLN group
    shifted_values: Dict[int, str] = {}  # Maps policy_idx -> shifted start_term value
    
    for op_dln, policy_list in dln_policies.items():
        print(f"[DEBUG] Processing DLN {op_dln} with {len(policy_list)} same-DLN policies")
        
        if len(policy_list) < 2:
            # Only 1 policy in this DLN group, no shift needed
            policy_idx, operator = policy_list[0]
            original_value = operator.get("start_term", "")
            shifted_values[policy_idx] = original_value
            print(f"[DEBUG]   Only 1 policy for DLN {op_dln}, no shift: Policy {policy_idx} = {original_value}")
            continue
        
        # Capture all ORIGINAL start_term values in chronological order
        original_starts = {}
        for idx in range(len(policy_list)):
            policy_idx, operator = policy_list[idx]
            original_starts[idx] = operator.get("start_term", "")
            print(f"[DEBUG]   ORIGINAL[{idx}] Policy {policy_idx}: start_term={original_starts[idx]}")
        
        # SHIFT: shifted[i] = original[i-1] for i > 0; shifted[0] = original[0]
        # First, apply shifts to all policies BEFORE updating operator objects
        shifted_map = {}
        
        # Policy[0] keeps its original value
        policy_idx_0, _ = policy_list[0]
        shifted_map[policy_idx_0] = original_starts[0]
        shifted_values[policy_idx_0] = original_starts[0]
        print(f"[DEBUG]   SHIFTED[0] Policy {policy_idx_0}: <- {original_starts[0]} (unchanged, first in DLN group)")
        
        # Apply shift to remaining policies: shifted[i] = original[i-1]
        for idx in range(1, len(policy_list)):
            policy_idx, operator = policy_list[idx]
            new_val = original_starts[idx - 1]
            shifted_map[policy_idx] = new_val
            shifted_values[policy_idx] = new_val
            print(f"[DEBUG]   SHIFTED[{idx}] Policy {policy_idx}: <- {new_val}")
        
        # Now update all operator objects with their shifted values
        for idx in range(len(policy_list)):
            policy_idx, operator = policy_list[idx]
            if policy_idx in shifted_map:
                operator["start_term"] = shifted_map[policy_idx]
    
    # STEP 4: Filter operators to only include those matching header_dln
    # This must happen AFTER shifting to ensure we don't lose the data
    if header_dln:
        for policy in policies:
            if "operators" in policy:
                original_op_count = len(policy["operators"])
                policy["operators"] = [
                    op for op in policy["operators"]
                    if op.get("dln") == header_dln
                ]
                filtered_count = len(policy["operators"])
                if filtered_count < original_op_count:
                    print(f"[DEBUG] Policy: filtered operators {original_op_count} -> {filtered_count}")
    
    # STEP 5: Assign formatted shifted values to policies
    # Initialize start_of_earliest_term for ALL policies (even those with no operators)
    print(f"\n[DEBUG] Assigning shifted start_of_earliest_term to ALL policies...")
    for policy_idx, policy in enumerate(policies):
        # Use shifted value if available, otherwise empty string
        shifted_start_term = shifted_values.get(policy_idx, "")
        formatted = format_date_to_mmddyyyy(shifted_start_term) if shifted_start_term else ""
        policies[policy_idx]["start_of_earliest_term"] = formatted
        print(f"[DEBUG]   Policy {policy_idx}: start_of_earliest_term = '{formatted}' (from shift: '{shifted_start_term}')")

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
