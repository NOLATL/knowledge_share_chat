"""Delete placeholder demo companies and every dependent row.

No-intake session paths create shell companies ("Demo discovery company",
"Document demo company"). They pollute the cohort with identity-less records,
so this removes them entirely — sessions, answers, messages, documents/chunks,
relays, reports, respondents, embeddings, and their benchmark history. Real
(named) companies are never touched. Run a recompute afterwards so cohort
counts settle.
"""

from __future__ import annotations

from dataclasses import dataclass

from playbook_shared.db import connect

DEMO_COMPANY_NAMES = ("Demo discovery company", "Document demo company")


@dataclass(frozen=True)
class DemoCleanupSummary:
    companies: int
    respondents: int
    sessions: int
    answers: int


def delete_demo_companies(database_url: str | None = None) -> DemoCleanupSummary:
    conn = connect(database_url, register_vector_types=False)
    conn.autocommit = False  # all-or-nothing
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM companies WHERE name = ANY(%s)", (list(DEMO_COMPANY_NAMES),))
            company_ids = [row[0] for row in cur.fetchall()]
            if not company_ids:
                conn.commit()
                return DemoCleanupSummary(0, 0, 0, 0)

            cur.execute(
                "SELECT id FROM respondents WHERE company_id = ANY(%s)",
                (company_ids,),
            )
            respondent_ids = [row[0] for row in cur.fetchall()]
            cur.execute("SELECT id FROM sessions WHERE company_id = ANY(%s)", (company_ids,))
            session_ids = {row[0] for row in cur.fetchall()}
            if respondent_ids:
                cur.execute("SELECT id FROM sessions WHERE respondent_id = ANY(%s)", (respondent_ids,))
                session_ids |= {row[0] for row in cur.fetchall()}
            session_ids = list(session_ids)

            def _delete(sql: str, params) -> int:
                cur.execute(sql, params)
                return cur.rowcount

            answers = 0
            if session_ids:
                cur.execute(
                    "DELETE FROM document_chunks WHERE document_id IN "
                    "(SELECT id FROM documents WHERE session_id = ANY(%s) OR company_id = ANY(%s))",
                    (session_ids, company_ids),
                )
                _delete("DELETE FROM documents WHERE session_id = ANY(%s) OR company_id = ANY(%s)", (session_ids, company_ids))
                answers = _delete("DELETE FROM answers WHERE session_id = ANY(%s)", (session_ids,))
                _delete("DELETE FROM messages WHERE session_id = ANY(%s)", (session_ids,))
                _delete("DELETE FROM email_relays WHERE session_id = ANY(%s)", (session_ids,))
                _delete("DELETE FROM reports WHERE session_id = ANY(%s)", (session_ids,))
            _delete("DELETE FROM reports WHERE company_id = ANY(%s)", (company_ids,))
            if respondent_ids:
                _delete("DELETE FROM benchmarks WHERE respondent_id = ANY(%s)", (respondent_ids,))
                _delete("DELETE FROM respondent_embeddings WHERE respondent_id = ANY(%s)", (respondent_ids,))
            _delete("DELETE FROM company_benchmarks WHERE company_id = ANY(%s)", (company_ids,))
            sessions = _delete("DELETE FROM sessions WHERE id = ANY(%s)", (session_ids,)) if session_ids else 0
            respondents = _delete("DELETE FROM respondents WHERE company_id = ANY(%s)", (company_ids,))
            companies = _delete("DELETE FROM companies WHERE id = ANY(%s)", (company_ids,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return DemoCleanupSummary(
        companies=companies,
        respondents=respondents,
        sessions=sessions,
        answers=answers,
    )
