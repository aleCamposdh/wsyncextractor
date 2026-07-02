"""
Cliente REST para QuickBooks Online API v3.
"""
import requests
from datetime import datetime, timedelta, timezone

from qbo import storage
from qbo import oauth as qbo_oauth
import logger as _log

_logger = _log.get(__name__)

QBO_BASE = "https://quickbooks.api.intuit.com/v3/company"
MINOR_VERSION = "75"


class QBOAuthError(Exception):
    pass


class QBOClient:
    def __init__(self):
        tokens = storage.get_tokens()
        if not tokens:
            raise QBOAuthError("No conectado a QuickBooks. Conecta desde el panel lateral.")

        self._access_token  = tokens["access_token"]
        self._refresh_token = tokens["refresh_token"]
        self._realm_id      = tokens["realm_id"]
        self._expires_at    = datetime.fromisoformat(tokens["expires_at"])

        self._item_cache         = {}  # name.lower() → id
        self._custom_field_ids   = None  # {field_name → DefinitionId}
        self._sales_term_net15   = None  # SalesTermRef id for Net 15
        self._doc_num_counter    = None  # next DocNumber to assign

        self._maybe_refresh()

    # ── Auth ──────────────────────────────────────────────────────────────────

    def _maybe_refresh(self) -> None:
        now = datetime.now(timezone.utc)
        if self._expires_at - now < timedelta(minutes=5):
            try:
                data = qbo_oauth.refresh_tokens(self._refresh_token, self._realm_id)
                qbo_oauth.save_token_response(data)
                self._access_token = data["access_token"]
                self._refresh_token = data["refresh_token"]
                expires_in = int(data.get("expires_in", 3600))
                self._expires_at = now + timedelta(seconds=expires_in)
            except Exception as e:
                raise QBOAuthError(f"Token QBO expirado y no se pudo renovar: {e}")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Accept":        "application/json",
            "Content-Type":  "application/json",
        }

    def _url(self, path: str) -> str:
        return f"{QBO_BASE}/{self._realm_id}/{path}"

    # ── Low-level API ─────────────────────────────────────────────────────────

    def query(self, sql: str) -> list:
        resp = requests.get(
            self._url("query"),
            params={"query": sql, "minorversion": MINOR_VERSION},
            headers=self._headers(),
            timeout=30,
        )
        if resp.status_code == 401:
            raise QBOAuthError("Token QBO inválido. Reconecta QBO.")
        resp.raise_for_status()
        data = resp.json()
        qr = data.get("QueryResponse", {})
        for key, val in qr.items():
            if isinstance(val, list):
                return val
        return []

    def create(self, entity: str, body: dict) -> dict:
        resp = requests.post(
            self._url(entity.lower()),
            params={"minorversion": MINOR_VERSION},
            headers=self._headers(),
            json=body,
            timeout=30,
        )
        if resp.status_code == 401:
            raise QBOAuthError("Token QBO inválido. Reconecta QBO.")
        if not resp.ok:
            try:
                fault = resp.json().get("Fault", {})
                msg = fault.get("Error", [{}])[0].get("Detail", resp.text)
            except Exception:
                msg = resp.text
            raise Exception(f"QBO {entity} error {resp.status_code}: {msg}")
        data = resp.json()
        # QBO wraps the created entity in a key matching the entity name (capitalized)
        for key in (entity, entity.capitalize(), entity.title()):
            if key in data:
                return data[key]
        return data

    def fetch_company_info(self) -> dict:
        results = self.query("SELECT * FROM CompanyInfo")
        return results[0] if results else {}

    # ── Customers ─────────────────────────────────────────────────────────────

    def find_customer_by_name(self, display_name: str) -> dict | None:
        safe = display_name.replace("'", "\\'")
        results = self.query(f"SELECT * FROM Customer WHERE DisplayName = '{safe}' MAXRESULTS 1")
        return results[0] if results else None

    def find_customers_like(self, prefix: str, parent_only: bool = False) -> list:
        safe = prefix.replace("'", "\\'").replace("%", "\\%")
        sql = f"SELECT * FROM Customer WHERE DisplayName LIKE '{safe}%' MAXRESULTS 10"
        results = self.query(sql)
        if parent_only:
            results = [r for r in results if not r.get("Job")]
        return results

    def create_customer(
        self,
        display_name: str,
        parent_id: str = "",
        company_name: str = "",
        address: dict | None = None,
        print_on_check_name: str = "",
    ) -> dict:
        body: dict = {"DisplayName": display_name}
        if company_name:
            body["CompanyName"] = company_name
        if print_on_check_name:
            body["PrintOnCheckName"] = print_on_check_name
        if address and (address.get("street") or address.get("city") or address.get("zip")):
            bill = {}
            if address.get("street"):  bill["Line1"]                  = address["street"]
            if address.get("city"):    bill["City"]                   = address["city"]
            if address.get("state"):   bill["CountrySubDivisionCode"] = address["state"]
            if address.get("zip"):     bill["PostalCode"]             = address["zip"]
            if address.get("country"): bill["Country"]                = address["country"]
            if bill:
                body["BillAddr"] = bill
                body["ShipAddr"] = dict(bill)  # same as billing
        if parent_id:
            body["Job"] = True
            body["ParentRef"] = {"value": parent_id}
            body["BillWithParent"] = True
        return self.create("Customer", body)

    def _get_customer(self, customer_id: str) -> dict:
        resp = requests.get(
            self._url(f"customer/{customer_id}"),
            params={"minorversion": MINOR_VERSION},
            headers=self._headers(),
            timeout=30,
        )
        if not resp.ok:
            return {}
        return resp.json().get("Customer", {})

    @staticmethod
    def _short_lot(lot: str) -> str:
        """Acorta lot crudo a parte significativa.
        Regla: split por grupos de 2+ ceros, devolver último segmento no vacío.
        Ej: '00100108' → '108', '00100212' → '212', '108' → '108'.
        """
        if not lot:
            return lot
        import re as _re
        parts = _re.split(r"0{2,}", str(lot))
        candidates = [p for p in parts if p]
        if not candidates:
            stripped = str(lot).lstrip("0")
            return stripped or lot
        return candidates[-1]

    def get_or_create_parent_customer(self, builder_name: str) -> str:
        import re
        builder_name = re.sub(r"\s+", " ", builder_name or "").strip()
        if not builder_name:
            raise ValueError("builder_name vacío")

        # Exact match first
        c = self.find_customer_by_name(builder_name)
        if c and not c.get("Job"):
            return c["Id"]
        # LIKE match (handles "Lennar Homes" matching "Lennar Homes LLC")
        matches = self.find_customers_like(builder_name, parent_only=True)
        if matches:
            return matches[0]["Id"]
        # Fallback case-insensitive: usar primer token como prefijo + filtrar lower()
        first_token = builder_name.split()[0]
        if first_token and first_token.lower() != builder_name.lower():
            broad = self.find_customers_like(first_token, parent_only=True)
        else:
            broad = self.find_customers_like(first_token, parent_only=True)
        target = builder_name.lower()
        for cand in broad:
            disp = (cand.get("DisplayName") or "").strip().lower()
            if disp == target or disp.startswith(target) or target.startswith(disp):
                _logger.info(
                    "QBO: parent match case-insensitive — buscado='%s' encontrado='%s' (id=%s)",
                    builder_name, cand.get("DisplayName"), cand["Id"],
                )
                return cand["Id"]
        _logger.warning(
            "QBO: no se encontró parent existente para '%s'. Creando nuevo. "
            "Candidatos con prefijo '%s': %s",
            builder_name, first_token,
            [c.get("DisplayName") for c in broad] or "ninguno",
        )
        result = self.create_customer(builder_name)
        _logger.info("QBO: cliente creado — %s (id=%s)", builder_name, result["Id"])
        return result["Id"]

    def _get_sub_customers(self, parent_id: str) -> list:
        """Fetch all sub-customers of parent via FullyQualifiedName LIKE query.

        QBO IDS does not support WHERE ParentRef filter, so we look up the
        parent's DisplayName via REST and use FullyQualifiedName LIKE instead.
        """
        resp = requests.get(
            self._url(f"customer/{parent_id}"),
            params={"minorversion": MINOR_VERSION},
            headers=self._headers(),
            timeout=30,
        )
        if not resp.ok:
            _logger.warning("QBO: no se pudo obtener cliente parent %s (%s)", parent_id, resp.status_code)
            return []
        parent_display = resp.json().get("Customer", {}).get("DisplayName", "")
        if not parent_display:
            return []
        safe = parent_display.replace("'", "\\'")
        try:
            results = self.query(
                f"SELECT * FROM Customer WHERE FullyQualifiedName LIKE '{safe}:%' MAXRESULTS 200"
            )
            _logger.info("QBO: sub-clientes de '%s': %d encontrados", parent_display, len(results))
            return results
        except Exception as e:
            _logger.warning("QBO: _get_sub_customers error: %s", e)
            return []

    def _find_sub_by_lot(self, subs: list, lot: str) -> str | None:
        """Search sub-customer list locally for one whose DisplayName contains this LOT number."""
        short = self._short_lot(lot)
        lot_stripped = lot.lstrip("0") or lot
        candidates = []
        for c in (short, lot_stripped, lot):
            if c and c not in candidates:
                candidates.append(c)
        for sc in subs:
            disp = (sc.get("DisplayName") or "").upper()
            for search_lot in candidates:
                if f"LOT {search_lot}" in disp:
                    _logger.info("QBO: sub-cliente encontrado por LOT %s → %s", search_lot, sc.get("DisplayName"))
                    return sc["Id"]
        return None

    def get_or_create_sub_customer(
        self,
        community_name: str,
        lot: str,
        parent_id: str,
        address: dict | None = None,
    ) -> str:
        short_lot = self._short_lot(lot) if lot else ""
        sub_name  = f"{community_name.upper()} LOT {short_lot}" if short_lot else community_name

        # 1. Exact match on preferred name
        c = self.find_customer_by_name(sub_name)
        if c:
            return c["Id"]

        # 2. Fetch all sub-customers of this parent, search locally by LOT number
        if lot:
            subs = self._get_sub_customers(parent_id)
            found_id = self._find_sub_by_lot(subs, lot)
            if found_id:
                return found_id

        # 3. Exact match on community name alone (legacy entries without lot)
        c = self.find_customer_by_name(community_name)
        if c:
            return c["Id"]

        # 4. Create new — set CompanyName = parent DisplayName + address + print-on-check
        parent = self._get_customer(parent_id)
        parent_display = parent.get("DisplayName", "")
        result = self.create_customer(
            sub_name,
            parent_id=parent_id,
            company_name=parent_display,
            address=address,
            print_on_check_name=sub_name,
        )
        _logger.info("QBO: sub-cliente creado — %s (id=%s)", sub_name, result["Id"])
        return result["Id"]

    def resolve_customer_id(
        self,
        builder: str,
        community: str,
        lot: str = "",
        address: dict | None = None,
    ) -> str:
        """Returns the QBO customer ID to use for the invoice."""
        parent_id = self.get_or_create_parent_customer(builder)
        if community:
            return self.get_or_create_sub_customer(community, lot, parent_id, address=address)
        return parent_id

    # ── Items (Products & Services) ───────────────────────────────────────────

    def get_or_create_item(self, name: str) -> str:
        key = name.lower()
        if key in self._item_cache:
            return self._item_cache[key]

        results = self.query(f"SELECT * FROM Item WHERE Name = '{name.replace(chr(39), chr(92)+chr(39))}' AND Active = true MAXRESULTS 1")
        if results:
            item_id = results[0]["Id"]
            self._item_cache[key] = item_id
            return item_id

        # Find an income account to attach
        accounts = self.query("SELECT * FROM Account WHERE AccountType = 'Income' AND Active = true MAXRESULTS 1")
        income_ref = {"value": accounts[0]["Id"]} if accounts else {"name": "Services"}

        body = {
            "Name": name,
            "Type": "Service",
            "IncomeAccountRef": income_ref,
        }
        result = self.create("Item", body)
        item_id = result["Id"]
        self._item_cache[key] = item_id
        _logger.info("QBO: item creado — %s (id=%s)", name, item_id)
        return item_id

    # ── Custom Fields ─────────────────────────────────────────────────────────

    def get_custom_field_ids(self) -> dict:
        """Returns custom field DefinitionId mapping for this QBO company.

        QBO assigns sequential DefinitionIds (1, 2, 3) to the three custom
        field slots. The Preferences API for this account does not return
        user-defined names/DefinitionIds in its CustomField array, so we
        use the known field names from the invoice form as a static mapping.
        """
        if self._custom_field_ids is not None:
            return self._custom_field_ids

        # Known custom fields visible in QBO invoice form (in creation order)
        self._custom_field_ids = {
            "ORDER NUMBER":  "1",
            "FECHA ENVIADO": "2",
            "NOTAS":         "3",
        }
        _logger.info("QBO: usando custom field mapping estático: %s", self._custom_field_ids)
        return self._custom_field_ids

    # ── Sales Terms ───────────────────────────────────────────────────────────

    def get_net15_term_id(self) -> str | None:
        if self._sales_term_net15 is not None:
            return self._sales_term_net15

        terms = self.query("SELECT * FROM Term WHERE Active = true")
        for t in terms:
            name = (t.get("Name") or "").lower()
            if "net 15" in name or "net15" in name:
                self._sales_term_net15 = t["Id"]
                return t["Id"]
        return None

    # ── DocNumber (Invoice Number) ────────────────────────────────────────────

    def _next_doc_number(self) -> str:
        """Generate sequential DocNumber. QBO won't auto-assign when
        CustomTxnNumbers=true, so we query max existing and increment locally.
        """
        if self._doc_num_counter is None:
            try:
                results = self.query(
                    "SELECT DocNumber FROM Invoice ORDERBY MetaData.CreateTime DESC MAXRESULTS 100"
                )
                max_num = 0
                for inv in results:
                    doc = str(inv.get("DocNumber", "") or "").strip()
                    try:
                        n = int(doc)
                        if n > max_num:
                            max_num = n
                    except (ValueError, TypeError):
                        continue
                self._doc_num_counter = max_num + 1 if max_num > 0 else 1001
                _logger.info("QBO: DocNumber counter inicializado en %d", self._doc_num_counter)
            except Exception as e:
                from datetime import datetime as _dt
                self._doc_num_counter = int(_dt.now().strftime("%y%m%d%H%M"))
                _logger.warning("QBO: max DocNumber falló (%s). Fallback: %d", e, self._doc_num_counter)

        n = self._doc_num_counter
        self._doc_num_counter += 1
        return str(n)

    # ── Invoices ──────────────────────────────────────────────────────────────

    def create_invoice(
        self,
        customer_id: str,
        txn_date: str,
        amount: float,
        service_type: str,
        order_number: str,
        cleaner: str = "",
    ) -> dict:
        item_id   = self.get_or_create_item(service_type)
        cf_ids    = self.get_custom_field_ids()
        term_id   = self.get_net15_term_id()

        # Memo: "{Servicio title-case} {Cleaner} · {OrderNumber}".
        # Ej: "Rough Clean MARIA · AWK00_005363".
        service_pretty = service_type.title() if service_type else ""
        base = f"{service_pretty} {cleaner}".strip() if cleaner else service_pretty
        memo = f"{base} · {order_number}" if order_number else base

        # Due date = txn_date + 15 days
        from datetime import date
        txn = date.fromisoformat(txn_date)
        due = (txn + timedelta(days=15)).isoformat()

        body: dict = {
            "CustomerRef": {"value": customer_id},
            "DocNumber":   self._next_doc_number(),
            "TxnDate":     txn_date,
            "DueDate":     due,
            "PrivateNote": memo,
            "PONumber":    order_number,
            "Line": [{
                "Amount":     round(amount, 2),
                "DetailType": "SalesItemLineDetail",
                "Description": service_type,
                "SalesItemLineDetail": {
                    "ItemRef":   {"value": item_id},
                    "Qty":       1,
                    "UnitPrice": round(amount, 2),
                },
            }],
        }

        if term_id:
            body["SalesTermRef"] = {"value": term_id}

        # Build custom fields — keys normalized to UPPER for reliable lookup
        custom_fields = []
        cf_map = {
            "ORDER NUMBER":  order_number,
            "FECHA ENVIADO": "",
            "NOTAS":         "",
        }
        for field_name, field_value in cf_map.items():
            def_id = cf_ids.get(field_name.upper().strip())
            if def_id:
                custom_fields.append({
                    "DefinitionId": def_id,
                    "Name":         field_name,
                    "Type":         "StringType",
                    "StringValue":  field_value,
                })
        if custom_fields:
            body["CustomField"] = custom_fields

        return self.create("Invoice", body)
