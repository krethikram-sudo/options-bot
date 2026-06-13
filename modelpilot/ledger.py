"""Counterfactual savings ledger (SQLite).

One row per gateway request: what was asked for, what the router said, what
actually ran, exact token usage from the API, and the Layer-1 cost estimates.
Prompt text is never stored.
"""

import sqlite3
import threading
import time
import uuid

from .pricing import Usage, baseline_cost, request_cost

_SCHEMA = """
CREATE TABLE IF NOT EXISTS requests (
    id TEXT PRIMARY KEY,
    ts REAL NOT NULL,
    mode TEXT NOT NULL,                -- shadow | advise | autopilot
    original_model TEXT NOT NULL,      -- what the caller asked for (the baseline)
    recommended_model TEXT NOT NULL,
    routed_model TEXT NOT NULL,        -- what actually ran
    applied INTEGER NOT NULL,          -- 1 if the gateway changed the model
    action TEXT NOT NULL,              -- switch | stay
    confidence REAL NOT NULL,
    category TEXT NOT NULL,
    rationale TEXT NOT NULL,
    status_code INTEGER,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens INTEGER NOT NULL DEFAULT 0,
    cache_write_tokens INTEGER NOT NULL DEFAULT 0,
    actual_cost REAL,
    baseline_cost REAL,                -- same tokens re-priced at original_model
    routed_cost REAL,                  -- same tokens re-priced at recommended_model
    realized_saved REAL,               -- baseline - actual (0 unless applied)
    potential_saved REAL,              -- baseline - routed (what following advice saves)
    arm TEXT NOT NULL DEFAULT 'observe',  -- treatment | control | observe
    retry_of TEXT,                     -- request id this re-run escalates (quality failure)
    session_key TEXT NOT NULL DEFAULT ''  -- conversation identity (for arm + continuation model)
);
CREATE INDEX IF NOT EXISTS idx_requests_ts ON requests (ts);
CREATE INDEX IF NOT EXISTS idx_requests_category ON requests (category);
CREATE INDEX IF NOT EXISTS idx_requests_session ON requests (session_key);
CREATE TABLE IF NOT EXISTS feedback (
    request_id TEXT NOT NULL,
    ts REAL NOT NULL,
    signal TEXT NOT NULL,              -- negative | positive
    note TEXT
);
CREATE INDEX IF NOT EXISTS idx_feedback_request ON feedback (request_id);
CREATE TABLE IF NOT EXISTS captures (
    request_id TEXT PRIMARY KEY,
    ts REAL NOT NULL,
    category TEXT NOT NULL,
    confidence REAL NOT NULL,
    prompt TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS replay_calibration (
    category TEXT NOT NULL,
    baseline_model TEXT NOT NULL,
    output_ratio REAL NOT NULL,        -- baseline output tokens / routed output tokens
    n INTEGER NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (category, baseline_model)
);
"""


class Ledger:
    def __init__(self, path: str = "modelpilot.db"):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def record(self, *, mode, recommendation, routed_model, applied, status_code, usage: Usage,
               arm: str = "observe", retry_of: str | None = None,
               request_id: str | None = None, session_key: str = "") -> str:
        actual = request_cost(routed_model, usage)
        base = baseline_cost(recommendation.original_model, usage)
        routed = request_cost(recommendation.recommended_model, usage)
        # Realized whenever the request ran below its baseline — whether the
        # gateway switched it (autopilot) or the caller followed advice and
        # declared the baseline via x-modelpilot-baseline (advise mode).
        ran_below_baseline = routed_model != recommendation.original_model
        realized = (base - actual) if (ran_below_baseline and base is not None and actual is not None) else 0.0
        potential = (base - routed) if (base is not None and routed is not None) else None
        request_id = request_id or uuid.uuid4().hex
        with self._lock:
            self._conn.execute(
                """INSERT INTO requests (
                       id, ts, mode, original_model, recommended_model, routed_model,
                       applied, action, confidence, category, rationale, status_code,
                       input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
                       actual_cost, baseline_cost, routed_cost, realized_saved, potential_saved,
                       arm, retry_of, session_key
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    request_id,
                    time.time(),
                    mode,
                    recommendation.original_model,
                    recommendation.recommended_model,
                    routed_model,
                    int(applied),
                    recommendation.action,
                    recommendation.confidence,
                    recommendation.category,
                    recommendation.rationale,
                    status_code,
                    usage.input_tokens,
                    usage.output_tokens,
                    usage.cache_read_input_tokens,
                    usage.cache_creation_input_tokens,
                    actual,
                    base,
                    routed,
                    realized,
                    potential,
                    arm,
                    retry_of,
                    session_key,
                ),
            )
            self._conn.commit()
        return request_id

    def record_feedback(self, request_id: str, signal: str, note: str | None = None):
        with self._lock:
            self._conn.execute(
                "INSERT INTO feedback (request_id, ts, signal, note) VALUES (?,?,?,?)",
                (request_id, time.time(), signal, note),
            )
            self._conn.commit()

    def record_capture(self, request_id: str, category: str, confidence: float, prompt: str):
        """Opt-in prompt capture for golden-set building. Only called when
        MODELPILOT_CAPTURE_PCT > 0 — by default no prompt text is ever stored."""
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO captures (request_id, ts, category, confidence, prompt) "
                "VALUES (?,?,?,?,?)",
                (request_id, time.time(), category, confidence, prompt),
            )
            self._conn.commit()

    def captures(self, since_ts: float = 0.0) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT request_id, ts, category, confidence, prompt FROM captures "
                "WHERE ts >= ? ORDER BY ts",
                (since_ts,),
            ).fetchall()
        return [dict(r) for r in rows]

    # --- Layer-2 replay calibration (see SAVINGS_DASHBOARD.md §1) ----------

    def replayable_sample(self, since_ts: float = 0.0, limit: int = 50) -> list[dict]:
        """Switch-recommended requests that have a captured prompt — the only
        rows replay can use, by design (no prompt text outside opt-in capture)."""
        with self._lock:
            rows = self._conn.execute(
                """SELECT r.id, r.category, r.original_model, r.routed_model,
                          r.output_tokens, c.prompt
                   FROM requests r JOIN captures c ON c.request_id = r.id
                   WHERE r.ts >= ? AND r.action = 'switch' AND r.output_tokens > 0
                   ORDER BY RANDOM() LIMIT ?""",
                (since_ts, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def set_replay_coefficient(self, category: str, baseline_model: str,
                               output_ratio: float, n: int):
        with self._lock:
            self._conn.execute(
                """INSERT INTO replay_calibration (category, baseline_model, output_ratio, n, updated_at)
                   VALUES (?,?,?,?,?)
                   ON CONFLICT(category, baseline_model)
                   DO UPDATE SET output_ratio=excluded.output_ratio, n=excluded.n,
                                 updated_at=excluded.updated_at""",
                (category, baseline_model, output_ratio, n, time.time()),
            )
            self._conn.commit()

    def replay_coefficients(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT category, baseline_model, output_ratio, n, updated_at "
                "FROM replay_calibration ORDER BY category"
            ).fetchall()
        return [dict(r) for r in rows]

    def corrected_potential(self, since_ts: float = 0.0) -> dict:
        """Potential savings with the output-length bias corrected: the Layer-1
        estimate re-prices the ROUTED model's output tokens at baseline rates,
        but the baseline would have produced ratio× as many output tokens.
        correction per group = sum(output_tokens) × baseline_out_price × (ratio − 1).
        """
        from .pricing import resolve_price

        coefficients = {(c["category"], c["baseline_model"]): c["output_ratio"]
                        for c in self.replay_coefficients()}
        with self._lock:
            rows = self._conn.execute(
                """SELECT category, original_model,
                          COALESCE(SUM(output_tokens), 0) out_tokens,
                          COALESCE(SUM(potential_saved), 0) potential
                   FROM requests
                   WHERE ts >= ? AND action = 'switch'
                   GROUP BY category, original_model""",
                (since_ts,),
            ).fetchall()
        raw = corrected = 0.0
        covered = set()
        for r in rows:
            raw += r["potential"]
            adjustment = 0.0
            ratio = coefficients.get((r["category"], r["original_model"]))
            price = resolve_price(r["original_model"])
            if ratio is not None and price is not None:
                adjustment = r["out_tokens"] * (price.output_per_mtok / 1e6) * (ratio - 1)
                covered.add(r["category"])
            corrected += r["potential"] + adjustment
        return {"raw_potential": raw, "corrected_potential": corrected,
                "covered_categories": sorted(covered)}

    def arm_costs(self, since_ts: float = 0.0) -> dict[str, list[float]]:
        """Per-request actual costs by holdout arm (autopilot traffic only)."""
        with self._lock:
            rows = self._conn.execute(
                """SELECT arm, actual_cost FROM requests
                   WHERE ts >= ? AND mode = 'autopilot' AND actual_cost IS NOT NULL
                         AND arm IN ('treatment', 'control')""",
                (since_ts,),
            ).fetchall()
        out: dict[str, list[float]] = {"treatment": [], "control": []}
        for r in rows:
            out[r["arm"]].append(r["actual_cost"])
        return out

    def quality_guardrails(self, since_ts: float = 0.0) -> list[dict]:
        """Negative-feedback rate per arm — the quality-parity check."""
        with self._lock:
            rows = self._conn.execute(
                """SELECT r.arm, COUNT(DISTINCT r.id) n,
                          COUNT(DISTINCT CASE WHEN f.signal = 'negative' THEN r.id END) n_negative
                   FROM requests r LEFT JOIN feedback f ON f.request_id = r.id
                   WHERE r.ts >= ? AND r.arm IN ('treatment', 'control')
                   GROUP BY r.arm""",
                (since_ts,),
            ).fetchall()
        return [dict(r) for r in rows]

    def escalation_costs(self, since_ts: float = 0.0) -> dict:
        """Re-runs linked via retry_of: count and total spend. Charged against
        realized savings — our mistakes are not free."""
        with self._lock:
            row = self._conn.execute(
                """SELECT COUNT(*) n, COALESCE(SUM(actual_cost), 0) cost
                   FROM requests WHERE ts >= ? AND retry_of IS NOT NULL""",
                (since_ts,),
            ).fetchone()
        return dict(row)

    def summary(self, since_ts: float = 0.0, gate: float = 0.0) -> dict:
        """`gated_potential` counts only switches whose confidence clears `gate`
        — i.e. what autopilot would actually apply at that gate. With the default
        gate=0 it equals `potential` (every recommendation)."""
        with self._lock:
            row = self._conn.execute(
                """SELECT COUNT(*) n,
                          COALESCE(SUM(input_tokens + cache_read_tokens + cache_write_tokens), 0) tok_in,
                          COALESCE(SUM(output_tokens), 0) tok_out,
                          COALESCE(SUM(actual_cost), 0) actual,
                          COALESCE(SUM(baseline_cost), 0) baseline,
                          COALESCE(SUM(realized_saved), 0) realized,
                          COALESCE(SUM(CASE WHEN action='switch' THEN potential_saved ELSE 0 END), 0) potential,
                          COALESCE(SUM(CASE WHEN action='switch' AND confidence >= ? THEN potential_saved ELSE 0 END), 0) gated_potential,
                          COALESCE(SUM(CASE WHEN action='switch' THEN 1 ELSE 0 END), 0) n_switch_recs,
                          COALESCE(SUM(applied), 0) n_applied
                   FROM requests WHERE ts >= ?""",
                (gate, since_ts),
            ).fetchone()
        return dict(row)

    def by_category(self, since_ts: float = 0.0) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                """SELECT category, COUNT(*) n,
                          COALESCE(SUM(actual_cost), 0) actual,
                          COALESCE(SUM(baseline_cost), 0) baseline,
                          COALESCE(SUM(CASE WHEN action='switch' THEN potential_saved ELSE 0 END), 0) potential,
                          AVG(confidence) avg_confidence
                   FROM requests WHERE ts >= ?
                   GROUP BY category ORDER BY potential DESC""",
                (since_ts,),
            ).fetchall()
        return [dict(r) for r in rows]

    def model_mix(self, since_ts: float = 0.0) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                """SELECT original_model, recommended_model, COUNT(*) n
                   FROM requests WHERE ts >= ?
                   GROUP BY original_model, recommended_model ORDER BY n DESC""",
                (since_ts,),
            ).fetchall()
        return [dict(r) for r in rows]

    def turns_so_far(self, session_key: str) -> int:
        if not session_key:
            return 0
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) n FROM requests WHERE session_key = ?", (session_key,)
            ).fetchone()
        return row["n"]

    def session_lengths(self, since_ts: float = 0.0, max_sessions: int = 5000) -> list[int]:
        """Observed turns-per-conversation — feeds the continuation model."""
        with self._lock:
            rows = self._conn.execute(
                """SELECT COUNT(*) n FROM requests
                   WHERE ts >= ? AND session_key != ''
                   GROUP BY session_key ORDER BY MAX(ts) DESC LIMIT ?""",
                (since_ts, max_sessions),
            ).fetchall()
        return [r["n"] for r in rows]

    def session_summary(self, session_key: str) -> dict:
        """Live aggregates for one conversation — powers the dashboard's
        'this session' strip. No time window: a session is its own scope."""
        with self._lock:
            row = self._conn.execute(
                """SELECT COUNT(*) n,
                          COALESCE(SUM(applied), 0) n_applied,
                          COALESCE(SUM(actual_cost), 0) actual,
                          COALESCE(SUM(baseline_cost), 0) baseline,
                          COALESCE(SUM(realized_saved), 0) realized,
                          COALESCE(SUM(CASE WHEN action='switch' THEN potential_saved ELSE 0 END), 0) potential,
                          MAX(ts) last_ts
                   FROM requests WHERE session_key = ?""",
                (session_key,),
            ).fetchone()
        return {"session_key": session_key, **dict(row)}

    def recent_sessions(self, limit: int = 15) -> list[dict]:
        """Most recently active conversations with their savings — the
        trackable history view."""
        with self._lock:
            rows = self._conn.execute(
                """SELECT session_key, COUNT(*) n,
                          COALESCE(SUM(applied), 0) n_applied,
                          COALESCE(SUM(actual_cost), 0) actual,
                          COALESCE(SUM(baseline_cost), 0) baseline,
                          COALESCE(SUM(realized_saved), 0) realized,
                          COALESCE(SUM(CASE WHEN action='switch' THEN potential_saved ELSE 0 END), 0) potential,
                          MIN(ts) first_ts, MAX(ts) last_ts
                   FROM requests WHERE session_key != ''
                   GROUP BY session_key ORDER BY last_ts DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def daily_series(self, since_ts: float = 0.0) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                """SELECT date(ts, 'unixepoch') day, COUNT(*) n,
                          COALESCE(SUM(actual_cost), 0) actual,
                          COALESCE(SUM(baseline_cost), 0) baseline,
                          COALESCE(SUM(realized_saved), 0) realized,
                          COALESCE(SUM(CASE WHEN action='switch' THEN potential_saved ELSE 0 END), 0) potential
                   FROM requests WHERE ts >= ?
                   GROUP BY day ORDER BY day""",
                (since_ts,),
            ).fetchall()
        return [dict(r) for r in rows]

    def daily_model_mix(self, since_ts: float = 0.0) -> list[dict]:
        """Per-day traffic share by recommended model — the migration story."""
        with self._lock:
            rows = self._conn.execute(
                """SELECT date(ts, 'unixepoch') day, recommended_model model, COUNT(*) n
                   FROM requests WHERE ts >= ?
                   GROUP BY day, model ORDER BY day""",
                (since_ts,),
            ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self._conn.close()
