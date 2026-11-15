import os
import json
import logging
import re
import time
import threading
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from .security_utils import sanitize_sensitive_text
from .. import PROJECT_ROOT

logger = logging.getLogger(__name__)

ACTIVITY_LOG_PATH = os.path.join(PROJECT_ROOT, "activity.log")
LAST_MAINT_PATH = os.path.join(PROJECT_ROOT, "last_maint.txt")
KL_TZ = ZoneInfo("Asia/Kuala_Lumpur")

INVENTORY_HEADERS = [
    "Item ID", "Name", "Category", "Qty", "Unit", "Location", "Min Qty",
    "Updated At", "Updated By",
]
INVENTORY_LOG_HEADERS = [
    "Timestamp", "Item ID", "Item", "Delta", "Reason", "Balance After", "By",
]


def _redact_log_text(value):
    if value is None:
        return ""
    text = str(value)
    text = re.sub(
        r'([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})',
        r'\1***@\2',
        text,
    )
    text = re.sub(r"\b\d{6,}\b", "***REDACTED***", text)
    return text

class Database:
    def __init__(self):
        self.sheet_id = os.getenv("SHEET_ID")
        self.google_json = os.getenv("GOOGLE_CREDENTIALS")
        self.registrations_sheet_name = os.getenv("REGISTRATIONS_SHEET_NAME", "STEM DB").strip() or "STEM DB"
        self.superadmin_ids = self._parse_ids("SUPERADMIN_IDS")
        self.admin_ids = self._parse_ids("ADMIN_IDS")
        
        self.cached_sheet_admins = [] 
        self.cached_sheet_logistics = []
        self.maintenance_mode = False
        self.last_config_refresh = 0
        
        self.student_cache = {}
        self.last_student_refresh = 0
        self.CACHE_TTL = 600
        self._student_refresh_lock = threading.Lock()
        self._student_refresh_in_progress = False
        
        self.logged_users_cache = set()
        
        self._init_maint_file()
        # Avoid blocking process startup on network I/O.
        threading.Thread(
            target=self.refresh_system_config,
            kwargs={"force": True},
            daemon=True
        ).start()

    def _init_maint_file(self):
        """Initializes the local maintenance tracking file if missing."""
        if not os.path.exists(LAST_MAINT_PATH):
            with open(LAST_MAINT_PATH, "w") as f:
                f.write("2000-01-01")

    def get_last_maintenance(self):
        """Returns the last maintenance date from local file."""
        try:
            if os.path.exists(LAST_MAINT_PATH):
                with open(LAST_MAINT_PATH, "r") as f:
                    return f.read().strip()
        except Exception:
            pass
        return "2000-01-01"

    def update_last_maintenance(self, date_value=None):
        """Updates the last maintenance/report date."""
        try:
            value = date_value or datetime.now(KL_TZ).strftime("%Y-%m-%d")
            with open(LAST_MAINT_PATH, "w") as f:
                f.write(value)
            return True
        except Exception as e:
            logger.error(f"Failed to update {LAST_MAINT_PATH}: {e}")
            return False

    def _parse_ids(self, env_key):
        raw = os.getenv(env_key, "")
        ids = set()
        if raw:
            try:
                ids = {int(x.strip()) for x in raw.split(",") if x.strip()}
            except ValueError:
                logger.error(f"⚠️ Error parsing {env_key}")
        return ids

    def get_sheet(self, sheet_name="Registrations"):
        try:
            scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

            if not self.sheet_id:
                logger.error("❌ CRITICAL: SHEET_ID missing!")
                return None
            
            if not self.google_json:
                # Fallback to local file if env var is missing
                if os.path.exists("service_account.json"):
                    with open("service_account.json") as f:
                        creds_dict = json.load(f)
                else:
                    logger.error("❌ CRITICAL: GOOGLE_CREDENTIALS missing!")
                    return None
            else:
                try:
                    creds_dict = json.loads(self.google_json)
                except json.JSONDecodeError:
                     # Fallback to local file on decode error
                    if os.path.exists("service_account.json"):
                        with open("service_account.json") as f:
                            creds_dict = json.load(f)
                    else:
                        logger.error("❌ JSON Decode Error in Env")
                        return None
                 
            creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
            client = gspread.authorize(creds)
            
            sh = client.open_by_key(self.sheet_id)
            
            # Main registrations tab is name-based, with legacy fallback to sheet1.
            if sheet_name == "Registrations":
                try:
                    return sh.worksheet(self.registrations_sheet_name)
                except gspread.WorksheetNotFound:
                    if self.registrations_sheet_name != "Registrations":
                        try:
                            return sh.worksheet("Registrations")
                        except gspread.WorksheetNotFound:
                            pass

                    try:
                        if sh.worksheets():
                            legacy_sheet = sh.sheet1
                            logger.warning(
                                "Registrations sheet '%s' not found, falling back to first tab '%s'.",
                                self.registrations_sheet_name,
                                legacy_sheet.title,
                            )
                            return legacy_sheet
                    except Exception:
                        pass

                    logger.error(
                        "Registrations sheet missing. Expected tab '%s' in spreadsheet %s.",
                        self.registrations_sheet_name,
                        self.sheet_id,
                    )
                    return None
                 
            try:
                return sh.worksheet(sheet_name)
            except gspread.WorksheetNotFound:
                # Auto-heal a missing sheet.
                ws = sh.add_worksheet(title=sheet_name, rows=100, cols=10)
                if sheet_name == "system_admins":
                    ws.append_row(["User ID", "Name", "Added By", "Role"])
                elif sheet_name == "system_config":
                    ws.append_row(["Key", "Value"])
                    ws.append_row(["maintenance_mode", "False"])
                elif sheet_name == "Inventory":
                    ws.append_row(INVENTORY_HEADERS)
                elif sheet_name == "InventoryLog":
                    ws.append_row(INVENTORY_LOG_HEADERS)
                return ws
                
        except Exception as e:
            logger.error(f"DB Connection Error ({sheet_name}): {e}")
            return None

    def refresh_system_config(self, force=False):
        """Reloads admins and config from sheet. Cached for 5 minutes."""
        if not force and (time.time() - self.last_config_refresh < 300):
            return

        try:
            ws_admins = self.get_sheet("system_admins")
            if ws_admins:
                self._ensure_sheet_headers(
                    ws_admins, ["User ID", "Name", "Added By", "Role"]
                )
                records = ws_admins.get_all_records()
                admin_ids = []
                logistics_ids = []
                for record in records:
                    raw_id = str(record.get("User ID", "")).strip()
                    if not raw_id.isdigit():
                        continue
                    role = str(record.get("Role", "")).strip().lower()
                    if role in ("logistics", "logistic", "operation", "operations", "ops"):
                        logistics_ids.append(int(raw_id))
                    else:
                        admin_ids.append(int(raw_id))
                self.cached_sheet_admins = admin_ids
                self.cached_sheet_logistics = logistics_ids
            
            ws_config = self.get_sheet("system_config")
            if ws_config:
                records = ws_config.get_all_records()
                for r in records:
                    if r['Key'] == 'maintenance_mode':
                        self.maintenance_mode = str(r['Value']).lower() == 'true'
            
            self.last_config_refresh = time.time()
            logger.info("System Config Refreshed (from Sheet)")
                        
        except Exception as e:
            logger.error(f"System Config Load Fail: {e}")

    def _ensure_sheet_headers(self, ws, headers):
        """Backfills missing header cells, e.g. adds a new 'Role' column."""
        try:
            current = ws.row_values(1)
        except Exception as e:
            logger.warning("Header read failed: %s", e)
            return
        for index, name in enumerate(headers):
            if index < len(current) and str(current[index]).strip():
                continue
            try:
                ws.update_cell(1, index + 1, name)
            except Exception as e:
                logger.warning("Header migrate failed (%s): %s", name, e)

    def is_superadmin(self, user_id):
        return user_id in self.superadmin_ids

    def is_admin(self, user_id):
        return (user_id in self.superadmin_ids or 
                user_id in self.admin_ids or 
                user_id in self.cached_sheet_admins)

    def is_logistics(self, user_id):
        return user_id in getattr(self, "cached_sheet_logistics", [])

    def is_inventory_user(self, user_id):
        """Inventory is for dedicated logistics accounts, not admins/superadmins."""
        return self.is_logistics(user_id) and not self.is_admin(user_id)

    def get_all_admin_ids(self):
        """Returns a set of ALL admin IDs (Super + Env + Sheet)."""
        return set(self.superadmin_ids) | set(self.admin_ids) | set(self.cached_sheet_admins)

    def set_maintenance(self, enabled: bool):
        try:
            ws = self.get_sheet("system_config")
            cell = ws.find("maintenance_mode")
            ws.update_cell(cell.row, cell.col + 1, str(enabled))
            self.maintenance_mode = enabled
            return True
        except Exception as e:
            logger.error(f"Set Maint Error: {e}")
            return False

    def add_admin(self, user_id, name, added_by, role="Admin"):
        try:
            ws = self.get_sheet("system_admins")
            self._ensure_sheet_headers(
                ws, ["User ID", "Name", "Added By", "Role"]
            )
            ws.append_row([str(user_id), name, added_by, role])
            self.refresh_system_config(force=True)
            return True
        except Exception as e:
            logger.error(f"Add Admin Error: {e}")
            return False

    def remove_admin(self, user_id):
        try:
            ws = self.get_sheet("system_admins")
            cell = ws.find(str(user_id), in_column=1)
            if not cell:
                return False
            ws.delete_rows(cell.row)
            self.refresh_system_config(force=True)
            return True
        except Exception as e:
            logger.error(f"Del Admin Error: {e}")
            return False

    def list_sheet_accounts(self):
        """Returns sheet-managed admin/logistics accounts with names and roles."""
        ws = self.get_sheet("system_admins")
        if not ws:
            return []
        try:
            self._ensure_sheet_headers(
                ws, ["User ID", "Name", "Added By", "Role"]
            )
            records = ws.get_all_records()
        except Exception as e:
            logger.error("List Accounts Error: %s", e)
            return []

        accounts = []
        for record in records:
            raw_id = str(record.get("User ID", "")).strip()
            if not raw_id.isdigit():
                continue
            accounts.append(
                {
                    "id": int(raw_id),
                    "name": str(record.get("Name", "")).strip(),
                    "role": str(record.get("Role", "")).strip() or "Admin",
                    "added_by": str(record.get("Added By", "")).strip(),
                }
            )
        return accounts

    def has_sheet_account(self, user_id):
        """True if the ID already has a row in system_admins (any role)."""
        try:
            target = int(user_id)
        except (TypeError, ValueError):
            return False
        return any(account["id"] == target for account in self.list_sheet_accounts())

    def update_admin_name(self, user_id, name):
        """Stores the resolved @username/display name for a managed account."""
        ws = self.get_sheet("system_admins")
        if not ws:
            return False
        try:
            cell = ws.find(str(user_id), in_column=1)
            if not cell:
                return False
            ws.update_cell(cell.row, 2, name)
            return True
        except Exception as e:
            logger.error("Update Admin Name Error: %s", e)
            return False

    def refresh_student_cache(self, force=False):
        """Loads all students into memory. 0 API calls for subsequent reads."""
        if not force and (time.time() - self.last_student_refresh < self.CACHE_TTL):
            return

        try:
            ws = self.get_sheet("Registrations")
            if not ws:
                return
            

            all_rows = ws.get_all_values()
            
            cache = {}
            for i, row in enumerate(all_rows[1:], start=2):
                # Sheet columns: A(0)=Time, B=Email, C=Name, D(3)=Matric, E=Courses, J(9)=IC, Q(16)=Receipt, R(17)=Status
                if len(row) > 3:
                    mat = str(row[3]).strip().upper()
                    if mat:
                        if mat not in cache:
                            cache[mat] = []
                        cache[mat].append((row, i))
            
            self.student_cache = cache
            self.last_student_refresh = time.time()
            logger.info(f"Student Cache Refreshed: {len(cache)} records.")
            
        except Exception as e:
            logger.error(f"Cache Refresh Error: {e}")

    def _start_student_cache_refresh(self):
        """Refresh the student cache in the background if it is stale."""
        with self._student_refresh_lock:
            if self._student_refresh_in_progress:
                return False
            self._student_refresh_in_progress = True

        def _worker():
            try:
                self.refresh_student_cache(force=True)
            finally:
                with self._student_refresh_lock:
                    self._student_refresh_in_progress = False

        threading.Thread(target=_worker, daemon=True).start()
        return True

    def find_member(self, matric):
        matric = str(matric).strip().upper()

        # Serve the current cache immediately when we already have data.
        # If it is stale, refresh in the background so users do not wait on Sheets.
        if self.student_cache:
            if time.time() - self.last_student_refresh >= self.CACHE_TTL:
                self._start_student_cache_refresh()
        else:
            # Cold start only: block once to build the initial cache.
            self.refresh_student_cache(force=True)

        # Duplicate registrations keep every row; use the most recent (bottom-most).
        entries = self.student_cache.get(matric)
        return entries[-1] if entries else (None, None)

    def _parse_sheet_date(self, raw_value):
        """Parse common sheet date/time formats into datetime."""
        if raw_value is None:
            return None

        text = str(raw_value).strip()
        if not text or text == "-":
            return None

        try:
            iso_value = text.replace("Z", "+00:00")
            dt = datetime.fromisoformat(iso_value)
            return dt.replace(tzinfo=None)
        except Exception:
            pass

        formats = (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y",
            "%d-%m-%Y %H:%M:%S",
            "%d-%m-%Y",
        )
        for fmt in formats:
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        return None

    def _extract_birth_year(self, raw_value):
        """Extract birth year from sheet birthday value."""
        dt = self._parse_sheet_date(raw_value)
        now_year = datetime.now().year
        if dt and 1900 <= dt.year <= now_year:
            return str(dt.year)

        text = str(raw_value or "").strip()
        if not text or text == "-":
            return "Unknown"

        # Prefer explicit 4-digit year.
        m = re.search(r"(19\d{2}|20\d{2})", text)
        if m:
            return m.group(1)

        return "Unknown"

    def _normalize_status(self, status_raw):
        """Normalize raw sheet status into approved/rejected/expired/pending."""
        status = str(status_raw or "").strip().lower()
        if status in ("expired", "expire", "tamat", "luput"):
            return "expired"
        if status in ("approved", "verified", "accept", "accepted"):
            return "approved"
        if status in ("rejected", "reject"):
            return "rejected"
        return "pending"

    def get_stats(self):
        """Returns secretary-focused monthly stats + expiry counters."""
        self.refresh_student_cache()

        now = datetime.now()
        window_start = now - timedelta(days=30)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if now.month == 12:
            next_month_start = month_start.replace(year=now.year + 1, month=1)
        else:
            next_month_start = month_start.replace(month=now.month + 1)

        total_last_30 = 0
        approved_last_30 = 0
        rejected_last_30 = 0
        pending_current = 0
        expiring_next_30 = 0
        expired_this_month = 0
        registered_current_month_names = []
        registered_all_names = []
        course_counts = {}
        birth_year_counts = {}
        demographic_total = 0

        for row, _ in (entry for entries in self.student_cache.values() for entry in entries):
            status = self._normalize_status(row[17] if len(row) > 17 else "")

            if status == "pending":
                pending_current += 1

            applied_at = self._parse_sheet_date(row[0] if len(row) > 0 else "")
            if applied_at and applied_at >= window_start:
                total_last_30 += 1
                if status == "approved":
                    approved_last_30 += 1
                elif status == "rejected":
                    rejected_last_30 += 1

            if (
                status == "approved"
                and applied_at
                and month_start <= applied_at < next_month_start
            ):
                name = str(row[2]).strip() if len(row) > 2 else ""
                if name:
                    registered_current_month_names.append(name)

            # Whole-DB demographic mix across all registered records.
            name_all = str(row[2]).strip() if len(row) > 2 else ""
            if name_all:
                registered_all_names.append(name_all)
            demographic_total += 1
            course = str(row[4]).strip() if len(row) > 4 and str(row[4]).strip() else "Unknown"
            birth_year = self._extract_birth_year(row[10] if len(row) > 10 else "")
            course_counts[course] = course_counts.get(course, 0) + 1
            birth_year_counts[birth_year] = birth_year_counts.get(birth_year, 0) + 1

            if status == "approved":
                entry_date = self._parse_sheet_date(row[13] if len(row) > 13 else "")
                if not entry_date:
                    continue

                expiry_date = entry_date + timedelta(days=365)
                if now <= expiry_date <= (now + timedelta(days=30)):
                    expiring_next_30 += 1
                if month_start <= expiry_date < next_month_start and expiry_date < now:
                    expired_this_month += 1

        decisions_last_30 = approved_last_30 + rejected_last_30
        approval_rate = (approved_last_30 / decisions_last_30 * 100.0) if decisions_last_30 else 0.0
        safe_total = max(demographic_total, 1)

        course_distribution = [
            {
                "label": course,
                "count": count,
                "pct": round((count / safe_total) * 100.0, 1),
            }
            for course, count in sorted(course_counts.items(), key=lambda item: item[1], reverse=True)
        ]
        birth_year_distribution = [
            {
                "label": year,
                "count": count,
                "pct": round((count / safe_total) * 100.0, 1),
            }
            for year, count in sorted(
                birth_year_counts.items(),
                key=lambda item: (item[0] == "Unknown", -item[1], item[0]),
            )
        ]

        return {
            "total_last_30": total_last_30,
            "approved_last_30": approved_last_30,
            "rejected_last_30": rejected_last_30,
            "pending_current": pending_current,
            "approval_rate": round(approval_rate, 1),
            "expiring_next_30": expiring_next_30,
            "expired_this_month": expired_this_month,
            "registered_current_month_count": len(registered_current_month_names),
            "registered_current_month_names": registered_current_month_names,
            "registered_all_count": len(registered_all_names),
            "registered_all_names": registered_all_names,
            "demographic_total": demographic_total,
            "course_distribution": course_distribution,
            "birth_year_distribution": birth_year_distribution,
        }

    def get_public_stats(self):
        """Returns sanitized public aggregate counts without any PII."""
        if self.student_cache:
            if time.time() - self.last_student_refresh >= self.CACHE_TTL:
                self._start_student_cache_refresh()
        else:
            self.refresh_student_cache(force=True)

        now = datetime.now()
        active_members = 0

        for entries in self.student_cache.values():
            if not entries:
                continue
            row, _ = entries[-1]
            status = self._normalize_status(row[17] if len(row) > 17 else "")
            if status != "approved":
                continue

            entry_raw = ""
            if len(row) > 13 and str(row[13]).strip():
                entry_raw = row[13]
            elif len(row) > 0:
                entry_raw = row[0]

            entry_dt = self._parse_sheet_date(entry_raw)
            if entry_dt and now >= (entry_dt + timedelta(days=365)):
                continue

            active_members += 1

        return {
            "active_members": active_members,
            "cached_at": int(self.last_student_refresh or 0),
        }

    def add_member(self, name, matric, ic, prog):
        sheet = self.get_sheet("Registrations")
        if sheet:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # New 18-col structure
            # A=Time, B=Email, C=Name, D=Matric, E=Courses, F-I, J=IC, K-Q, R=Status
            row = [""] * 18
            row[0] = timestamp
            row[1] = "bot_add"
            row[2] = name
            row[3] = matric
            row[4] = prog # Courses
            row[9] = ic   # IC Number
            row[17] = "Approved" # Status
            
            sheet.append_row(row)
            # Invalidate cache to force reload next time (simplest way to get correct row index)
            self.last_student_refresh = 0
            return True
        return False

    def get_members(self, limit=50):
        self.refresh_student_cache()
        all_values = [row for entries in self.student_cache.values() for row, idx in entries]
        return all_values[::-1][:limit]

    def search_members(self, query):
        self.refresh_student_cache()
        query = query.lower()
        matches = []
        for row, _ in (entry for entries in self.student_cache.values() for entry in entries):
            if len(row) > 9:
                name = row[2].lower()
                matric = row[3].lower()
                ic = str(row[9]).lower()
                
                if query in name or query in matric or query in ic:
                    matches.append(row)
        return matches

    def delete_member(self, matric):
        sheet = self.get_sheet("Registrations")
        if sheet:
            cell = sheet.find(matric, in_column=4)
            if cell:
                sheet.delete_rows(cell.row)
                
                if matric in self.student_cache:
                    del self.student_cache[matric]
                
                # Force full refresh next time so row indices stay consistent after deletion.
                self.last_student_refresh = 0
                    
                return True, cell.row
            return False, None
        return None, None

    def get_users_sheet(self):
        try:
             main_sheet = self.get_sheet("Registrations")
             if not main_sheet:
                 return None
             
             spreadsheet = main_sheet.spreadsheet
             try:
                 return spreadsheet.worksheet("Users")
             except gspread.WorksheetNotFound:
                 sheet = spreadsheet.add_worksheet(title="Users", rows=1000, cols=3)
                 sheet.append_row(["User ID", "Name", "Joined Date"])
                 return sheet
        except Exception as e:
            logger.error(f"Users Sheet Error: {e}")
            return None

    def log_user(self, user_id, name):
        """Logs user to sheet if not already logged this session. Blocking I/O."""
        if user_id in self.logged_users_cache:
            return
            
        try:
            self.logged_users_cache.add(user_id)
            
            sheet = self.get_users_sheet()
            if not sheet:
                return

            # Append without pre-reading to avoid an extra Sheets API call; get_all_users deduplicates on read.
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sheet.append_row([str(user_id), name, timestamp])
            
        except Exception as e:
            logger.error(f"Log User Error: {e}")

    def get_all_users(self):
        """Returns a unique list of all numeric user IDs from the log sheet."""
        sheet = self.get_users_sheet()
        if not sheet:
            return []

        try:
            # Col 1 is ID, row 1 is header "User ID".
            raw_ids = sheet.col_values(1)[1:]
            unique_ids = []
            seen = set()

            for raw_id in raw_ids:
                if not raw_id.isdigit():
                    continue

                user_id = int(raw_id)
                if user_id in seen:
                    continue

                seen.add(user_id)
                unique_ids.append(user_id)

            return unique_ids
        except Exception as e:
            logger.error(f"Get Users Error: {e}")
            return []

    def log_action(self, name, action, details, role="ADMIN"):
        """Logs actions to a local file for daily reporting."""
        timestamp = datetime.now(KL_TZ).strftime("%Y-%m-%d %H:%M:%S")
        safe_name = _redact_log_text(name)
        safe_details = _redact_log_text(details)
        log_entry = f"[{timestamp}] {role}: {safe_name} | ACTION: {action} | {safe_details}\n"
        
        try:
            with open(ACTIVITY_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception as e:
            logger.error(f"Failed to write to log: {e}")

    def get_unprocessed_registrations(self):
        """Finds rows where Resit (Col 8) is present but Status (Col 9) is Empty."""
        sheet = self.get_sheet("Registrations")
        if not sheet:
            return []
        try:
            all_values = sheet.get_all_values()
            unprocessed = []
            
            # Start from row 2 (index 1) to skip header
            for i, row in enumerate(all_values[1:], start=2):
                # We need Col Q (index 16) for Receipt.
                if len(row) <= 16:
                    continue
                
                receipt = row[16].strip()
                # Status is Col R (index 17).
                status = row[17].strip() if len(row) > 17 else ""
                status_norm = status.lower()

                # Treat fresh queue statuses as pending candidates.
                if receipt and (not status or status_norm == "pending admin approval" or status_norm == "pending"):
                    # Valid registration needing approval
                    unprocessed.append({
                        'row': i,
                        'data': row
                    })
            return unprocessed
        except Exception as e:
            logger.error(f"Error fetching members: {e}")
            return []
    def get_members_by_filter(self, status_filter):
        """Get members filtered by Status (Col I)."""
        sheet = self.get_sheet("Registrations")
        if not sheet:
            return []
        
        try:
            rows = sheet.get_all_values()
            filtered = []
            # Skip header (row 1)
            for i, row in enumerate(rows[1:], start=2):
                # Skip non-member / malformed rows.
                if len(row) <= 3:
                    continue
                name = str(row[2]).strip() if len(row) > 2 else ""
                matric = str(row[3]).strip() if len(row) > 3 else ""
                if not matric:
                    continue

                raw_status = row[17].strip().lower() if len(row) > 17 else ""

                if raw_status in ("expired", "expire", "tamat", "luput"):
                    status = "Expired"
                elif raw_status in ("approved", "verified", "✓", "âœ“"):
                    status = "Approved"
                elif raw_status in ("rejected", "reject"):
                    status = "Rejected"
                else:
                    status = "Pending"
                
                if status == status_filter:
                    filtered.append({
                        'row': i,
                        'name': name if name else "Unknown",
                        'matric': matric,
                        'ic': row[9] if len(row) > 9 else "Unknown", # J=9
                        'prog': row[4] if len(row) > 4 else "Unknown", # E=4
                        'status': status
                    })
            return filtered
        except Exception as e:
            logger.error(f"Error filtering members: {e}")
            return []
    def update_status(self, row_index, status):
        """Updates Column I (9) with status."""
        sheet = self.get_sheet("Registrations")
        if not sheet:
            return False
        try:
            # Column R (index 18) holds the status.
            sheet.update_cell(row_index, 18, status)
            return True
        except Exception as e:
            logger.error(f"Update Status Error: {e}")
            return False
    def update_status_by_row_or_matric(self, row_index, matric, status):
        """Safely updates status by row, with matric fallback if row shifted."""
        sheet = self.get_sheet("Registrations")
        if not sheet:
            return False
        target_row = row_index
        safe_matric = str(matric).strip().upper()
        try:
            row_values = sheet.row_values(target_row)
            row_matric = row_values[3].strip().upper() if len(row_values) > 3 else ""
            if row_matric != safe_matric:
                cell = sheet.find(safe_matric, in_column=4)
                if not cell:
                    return False
                target_row = cell.row

            sheet.update_cell(target_row, 18, status)
            self.last_student_refresh = 0
            return True
        except Exception as e:
            logger.error(f"Update Status Safe Error: {e}")
            return False

    def renew_membership_by_row_or_matric(self, row_index, matric):
        """Renew membership by extending expiry from max(current expiry, today) by 1 year."""
        sheet = self.get_sheet("Registrations")
        if not sheet:
            return {"ok": False, "error": "sheet_unavailable"}

        target_row = row_index
        safe_matric = str(matric).strip().upper()
        try:
            row_values = sheet.row_values(target_row)
            row_matric = row_values[3].strip().upper() if len(row_values) > 3 else ""
            if row_matric != safe_matric:
                cell = sheet.find(safe_matric, in_column=4)
                if not cell:
                    return {"ok": False, "error": "matric_not_found"}
                target_row = cell.row
                row_values = sheet.row_values(target_row)

            entry_raw = row_values[13] if len(row_values) > 13 else ""
            timestamp_raw = row_values[0] if len(row_values) > 0 else ""

            entry_dt = self._parse_sheet_date(entry_raw) or self._parse_sheet_date(timestamp_raw) or datetime.now()
            old_expiry_dt = entry_dt + timedelta(days=365)
            now_dt = datetime.now()
            renewal_anchor = old_expiry_dt if old_expiry_dt > now_dt else now_dt
            new_expiry_dt = renewal_anchor + timedelta(days=365)

            # Keep one active record: advance entry/start date and ensure approved status.
            sheet.update_cell(target_row, 14, renewal_anchor.strftime("%d/%m/%y"))  # N
            sheet.update_cell(target_row, 18, "Approved")  # R

            self.last_student_refresh = 0
            return {
                "ok": True,
                "row": target_row,
                "old_expiry": old_expiry_dt.strftime("%d/%m/%y"),
                "new_expiry": new_expiry_dt.strftime("%d/%m/%y"),
                "renewed_entry": renewal_anchor.strftime("%d/%m/%y"),
            }
        except Exception as e:
            logger.error("Renew Membership Safe Error: %s", sanitize_sensitive_text(e))
            return {"ok": False, "error": str(e)}

    def get_member_by_row_or_matric(self, row_index, matric):
        """Fetch a member row safely by row, fallback to matric search if row shifted."""
        sheet = self.get_sheet("Registrations")
        if not sheet:
            return None, None
        target_row = row_index
        safe_matric = str(matric).strip().upper()
        try:
            row_values = sheet.row_values(target_row)
            row_matric = row_values[3].strip().upper() if len(row_values) > 3 else ""
            if row_matric != safe_matric:
                cell = sheet.find(safe_matric, in_column=4)
                if not cell:
                    return None, None
                target_row = cell.row
                row_values = sheet.row_values(target_row)

            return row_values, target_row
        except Exception as e:
            logger.error(f"Get Member Safe Error: {e}")
            return None, None

    def delete_registration_by_row_or_matric(self, row_index, matric):
        """Safely deletes a registration by row, with matric fallback if row shifted."""
        sheet = self.get_sheet("Registrations")
        if not sheet:
            return False
        target_row = row_index
        safe_matric = str(matric).strip().upper()
        try:
            row_values = sheet.row_values(target_row)
            row_matric = row_values[3].strip().upper() if len(row_values) > 3 else ""
            if row_matric != safe_matric:
                cell = sheet.find(safe_matric, in_column=4)
                if not cell:
                    return False
                target_row = cell.row

            sheet.delete_rows(target_row)
            self.last_student_refresh = 0
            return True
        except Exception as e:
            logger.error(f"Delete Registration Safe Error: {e}")
            return False

    def get_inventory_items(self):
        """Returns all inventory rows as normalized dicts."""
        ws = self.get_sheet("Inventory")
        if not ws:
            return []
        try:
            rows = ws.get_all_values()
        except Exception as e:
            logger.error("Inventory read error: %s", e)
            return []

        items = []
        for i, row in enumerate(rows[1:], start=2):
            item_id = str(row[0]).strip() if len(row) > 0 else ""
            if not item_id:
                continue
            items.append(
                {
                    "row": i,
                    "id": item_id,
                    "name": str(row[1]).strip() if len(row) > 1 else "",
                    "category": str(row[2]).strip() if len(row) > 2 else "",
                    "qty": self._to_int(row[3] if len(row) > 3 else 0),
                    "unit": str(row[4]).strip() if len(row) > 4 else "",
                    "location": str(row[5]).strip() if len(row) > 5 else "",
                    "min_qty": self._to_int(row[6] if len(row) > 6 else 0),
                    "updated_at": str(row[7]).strip() if len(row) > 7 else "",
                    "updated_by": str(row[8]).strip() if len(row) > 8 else "",
                }
            )
        return items

    def _to_int(self, raw_value):
        try:
            return int(float(str(raw_value).strip() or 0))
        except (TypeError, ValueError):
            return 0

    def _append_inventory_log(self, item_id, name, delta, reason, balance, by, timestamp):
        log_ws = self.get_sheet("InventoryLog")
        if not log_ws:
            return
        try:
            log_ws.append_row(
                [timestamp, item_id, name, int(delta), reason, int(balance), by]
            )
        except Exception as e:
            logger.error("Inventory log append error: %s", e)

    def add_inventory_item(self, name, category, qty, unit, location, min_qty, by):
        """Creates an item with the next INV-### id and logs its opening stock."""
        ws = self.get_sheet("Inventory")
        if not ws:
            return {"ok": False, "error": "sheet_unavailable"}

        name = str(name or "").strip()
        if not name:
            return {"ok": False, "error": "invalid_name"}

        qty = self._to_int(qty)
        min_qty = self._to_int(min_qty)
        if qty < 0 or min_qty < 0:
            return {"ok": False, "error": "negative_qty"}

        max_num = 0
        for item in self.get_inventory_items():
            match = re.match(r"^INV-(\d+)$", item["id"], re.IGNORECASE)
            if match:
                max_num = max(max_num, int(match.group(1)))
        item_id = f"INV-{max_num + 1:03d}"

        now = datetime.now(KL_TZ).strftime("%Y-%m-%d %H:%M:%S")
        try:
            ws.append_row(
                [item_id, name, str(category or "").strip(), qty, str(unit or "").strip(),
                 str(location or "").strip(), min_qty, now, str(by)]
            )
        except Exception as e:
            logger.error("Inventory add error: %s", e)
            return {"ok": False, "error": "append_failed"}

        self._append_inventory_log(item_id, name, qty, "Opening stock", qty, by, now)
        return {"ok": True, "id": item_id, "name": name, "qty": qty}

    def adjust_inventory(self, item_id, delta, reason, by):
        """Applies a signed stock delta to one item and records the movement."""
        # shortcut: read-then-write is not atomic; two superadmins adjusting the
        # same item at once can lose one update. Upgrade to a Sheets batch/queue
        # if simultaneous edits become common.
        ws = self.get_sheet("Inventory")
        if not ws:
            return {"ok": False, "error": "sheet_unavailable"}

        item_id = str(item_id or "").strip().upper()
        delta = self._to_int(delta)
        if delta == 0:
            return {"ok": False, "error": "zero_delta"}

        try:
            cell = ws.find(item_id, in_column=1)
        except Exception as e:
            logger.error("Inventory lookup error: %s", e)
            return {"ok": False, "error": "lookup_failed"}
        if not cell:
            return {"ok": False, "error": "not_found"}

        try:
            row = ws.row_values(cell.row)
        except Exception as e:
            logger.error("Inventory row read error: %s", e)
            return {"ok": False, "error": "lookup_failed"}

        name = str(row[1]).strip() if len(row) > 1 else item_id
        current = self._to_int(row[3] if len(row) > 3 else 0)
        new_qty = current + delta
        if new_qty < 0:
            return {"ok": False, "error": "insufficient", "current": current}

        now = datetime.now(KL_TZ).strftime("%Y-%m-%d %H:%M:%S")
        try:
            ws.update_cell(cell.row, 4, new_qty)
            ws.update_cell(cell.row, 8, now)
            ws.update_cell(cell.row, 9, str(by))
        except Exception as e:
            logger.error("Inventory update error: %s", e)
            return {"ok": False, "error": "update_failed"}

        self._append_inventory_log(item_id, name, delta, reason or "Manual update", new_qty, by, now)
        return {
            "ok": True,
            "id": item_id,
            "name": name,
            "delta": delta,
            "current": current,
            "new_qty": new_qty,
        }

    def get_inventory_log(self, limit=50):
        """Returns the most recent inventory movements, newest first."""
        ws = self.get_sheet("InventoryLog")
        if not ws:
            return []
        try:
            rows = ws.get_all_values()
        except Exception as e:
            logger.error("Inventory log read error: %s", e)
            return []

        entries = []
        for row in rows[1:]:
            if len(row) < 5:
                continue
            entries.append(
                {
                    "timestamp": str(row[0]).strip(),
                    "item_id": str(row[1]).strip(),
                    "item": str(row[2]).strip(),
                    "delta": self._to_int(row[3]),
                    "reason": str(row[4]).strip(),
                    "balance": self._to_int(row[5] if len(row) > 5 else 0),
                    "by": str(row[6]).strip() if len(row) > 6 else "",
                }
            )
        return entries[-int(limit):][::-1]


db = Database()

