from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import streamlit as st


# ============================================================
# PROJECT PATH
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# EXISTING CV COMPONENTS
# ============================================================

from app.services.cv_ingestion_service import (
    CVIngestionService,
)


# ============================================================
# JOB DISCOVERY COMPONENTS
# ============================================================

from app.discovery.search_executor import (
    SearchExecutor,
)

from app.discovery.deduplicator import (
    SourceDeduplicator,
)

from app.discovery.normalizer import (
    normalize_jobs,
    save_jobs,
    OUTPUT_FILE,
)

from app.discovery.job_recency import (
    get_recent_jobs,
)

from app.discovery.deterministic_job_scorer import (
    score_job,
)

from app.storage.job_store import (
    JobStore,
)

from app.storage.database import (
    JobDatabase,
)


# ============================================================
# CONTACT / OUTREACH COMPONENTS
# ============================================================

from app.networking.company_domain_resolver import (
    CompanyDomainResolver,
)

from app.networking.hunter_client import (
    HunterClient,
)

from app.networking.contact_relevance import (
    ContactRelevanceAnalyzer,
)

from app.networking.contact_discovery import (
    ContactDiscovery,
)

from app.storage.contact_store import (
    ContactStore,
)

from app.networking.outreach_generator import (
    OutreachGenerator,
)

from app.networking.outreach_tracker import (
    OutreachTracker,
)

from app.networking.approval_processor import (
    ApprovalProcessor,
)


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="JobPilot",
    page_icon="🎯",
    layout="wide",
)
# ============================================================
# AUTHENTICATION
# ============================================================

def login_page() -> None:

    st.title("🎯 JobPilot")

    st.subheader(
        "Sign in to continue"
    )

    with st.form("login_form"):

        username = st.text_input(
            "Username"
        )

        password = st.text_input(
            "Password",
            type="password",
        )

        submitted = st.form_submit_button(
            "Login",
            type="primary",
            use_container_width=True,
        )

        if submitted:

            expected_username = (
                st.secrets["auth"]["username"]
            )

            expected_password = (
                st.secrets["auth"]["password"]
            )

            if (
                username == expected_username
                and password == expected_password
            ):

                st.session_state.authenticated = True

                st.rerun()

            else:

                st.error(
                    "Invalid username or password."
                )


if "authenticated" not in st.session_state:

    st.session_state.authenticated = False


if not st.session_state.authenticated:

    login_page()

    st.stop()
# -----------------------------
# LOGOUT
# -----------------------------

if st.session_state.authenticated:
    if st.sidebar.button(
        "Logout",
        use_container_width=True,
    ):
        st.session_state.authenticated = False
        st.rerun()

# ============================================================
# SESSION STATE
# ============================================================

if "recent_jobs" not in st.session_state:
    st.session_state.recent_jobs = []

if "search_completed" not in st.session_state:
    st.session_state.search_completed = False

if "contacts" not in st.session_state:
    st.session_state.contacts = {}

if "drafts" not in st.session_state:
    st.session_state.drafts = {}

if "send_results" not in st.session_state:
    st.session_state.send_results = {}

if "search_report" not in st.session_state:
    st.session_state.search_report = {}


# ============================================================
# HELPERS
# ============================================================


def load_candidate_profile() -> dict[str, Any]:
    profile_path = (
        PROJECT_ROOT
        / "data"
        / "candidate"
        / "current_profile.json"
    )

    if not profile_path.exists():
        return {}

    with profile_path.open(
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(file)


def is_ba_title(title: str | None) -> bool:

    value = (
        title or ""
    ).strip().lower()

    signals = (
        "business analyst",
        "senior business analyst",
        "lead business analyst",
        "principal business analyst",
    )

    return any(
        signal in value
        for signal in signals
    )


def get_job_key(job: dict[str, Any]) -> str:

    return (
        f"{job.get('source', '')}"
        f"::"
        f"{job.get('source_job_id', '')}"
    )


def get_contact_name(
    contact: dict[str, Any],
) -> str:

    return (
        contact.get("full_name")
        or contact.get("first_name")
        or "Unknown"
    )


def parse_matched_skills(
    job: dict[str, Any],
) -> list[str]:

    value = job.get(
        "matched_skills"
    )

    if not value:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, str):

        try:
            parsed = json.loads(value)

            if isinstance(
                parsed,
                list,
            ):
                return parsed

        except json.JSONDecodeError:
            pass

        return [value]

    return []


def format_score(
    score: Any,
) -> str:

    if score is None:
        return "N/A"

    try:
        return str(
            int(float(score))
        )

    except (
        TypeError,
        ValueError,
    ):
        return str(score)


# ============================================================
# JOB SEARCH PIPELINE
# ============================================================


def run_live_job_search() -> dict[str, Any]:

    executor = SearchExecutor()

    # SearchExecutor.run() returns the list of jobs.
    jobs = executor.run()

    # The execution metrics are persisted separately.
    report_path = (
        PROJECT_ROOT
        / "data"
        / "jobs"
        / "search_execution_report.json"
    )

    if report_path.exists():

        with report_path.open(
            "r",
            encoding="utf-8",
        ) as file:

            execution_report = json.load(file)

    else:

        execution_report = {}

    # --------------------------------------------------------
    # Load raw jobs
    # --------------------------------------------------------

    raw_jobs_path = (
        PROJECT_ROOT
        / "data"
        / "jobs"
        / "raw_jobs.json"
    )

    with raw_jobs_path.open(
        "r",
        encoding="utf-8",
    ) as file:

        raw_payload = json.load(file)

    if isinstance(
        raw_payload,
        dict,
    ):

        raw_jobs = raw_payload.get(
            "jobs",
            [],
        )

    else:

        raw_jobs = raw_payload

    # --------------------------------------------------------
    # Source deduplication
    # --------------------------------------------------------

    deduplicator = SourceDeduplicator()

    unique_jobs, dedup_report = (
        deduplicator.deduplicate(
            raw_jobs
        )
    )

    deduplicated_path = (
        PROJECT_ROOT
        / "data"
        / "jobs"
        / "source_deduplicated_jobs.json"
    )

    with deduplicated_path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            {
                "generated_at": (
                    dedup_report.get(
                        "generated_at"
                    )
                ),
                "total_jobs": len(
                    unique_jobs
                ),
                "jobs": unique_jobs,
            },
            file,
            indent=2,
            default=str,
        )

    # --------------------------------------------------------
    # Normalization
    # --------------------------------------------------------

    normalized_jobs = normalize_jobs(
        unique_jobs
    )

    save_jobs(
        normalized_jobs,
        OUTPUT_FILE,
    )

    # --------------------------------------------------------
    # SQLite
    # --------------------------------------------------------

    job_store = JobStore()

    ingest_result = job_store.ingest()

    # --------------------------------------------------------
    # Recency
    # --------------------------------------------------------

    recent_jobs = get_recent_jobs(
        days=7
    )

    # --------------------------------------------------------
    # Deterministic scoring
    # --------------------------------------------------------

    scored_jobs = []

    for job in recent_jobs:

        result = score_job(
            job
        )

        job_store.update_job_score(
            source=job[
                "source"
            ],
            source_job_id=job[
                "source_job_id"
            ],
            score_result=result,
        )

        enriched_job = dict(
            job
        )

        enriched_job.update(
            result
        )

        scored_jobs.append(
            enriched_job
        )

    job_store.database.connection.commit()

    # --------------------------------------------------------
    # Business Analyst hard inclusion
    # --------------------------------------------------------

    ba_jobs = [
        job
        for job in scored_jobs
        if is_ba_title(
            job.get("title")
        )
    ]

    ba_jobs.sort(
        key=lambda job: (
            job.get(
                "relevance_score"
            )
            or 0
        ),
        reverse=True,
    )

    st.session_state.recent_jobs = (
        ba_jobs
    )

    # --------------------------------------------------------
    # Build UI report
    # --------------------------------------------------------

    tasks_executed = (
        execution_report.get(
            "tasks_selected",
            execution_report.get(
                "tasks_executed",
                0,
            ),
        )
    )

    jobs_discovered = (
        execution_report.get(
            "raw_jobs_found",
            execution_report.get(
                "jobs_discovered",
                len(jobs),
            ),
        )
    )

    st.session_state.search_report = {

        "tasks_executed":
            tasks_executed,

        "jobs_discovered":
            jobs_discovered,

        "new_jobs":
            ingest_result.get(
                "NEW",
                0,
            ),

        "existing_jobs":
            ingest_result.get(
                "EXISTING",
                0,
            ),

        "updated_jobs":
            ingest_result.get(
                "UPDATED",
                0,
            ),

        "recent_jobs":
            len(
                recent_jobs
            ),

        "ba_jobs":
            len(
                ba_jobs
            ),
    }

    st.session_state.search_completed = True

    return (
        st.session_state.search_report
    )

# ============================================================
# CONTACT DISCOVERY
# ============================================================


def discover_contacts(
    job: dict[str, Any],
) -> dict[str, Any]:

    company = (
        job.get("company")
        or ""
    ).strip()

    if not company:

        return {
            "status": "ERROR",
            "message": "Job has no company.",
            "contacts": [],
        }

    # --------------------------------------------------------
    # Resolve company domain
    # --------------------------------------------------------

    resolver = CompanyDomainResolver()

    resolution = resolver.resolve(
        company
    )

    if resolution.status != "VERIFIED":

        resolution = resolver.discover_domain(
            company
        )

    if resolution.status != "VERIFIED":

        return {
            "status": "DOMAIN_UNRESOLVED",
            "message": (
                f"Could not resolve a verified "
                f"domain for {company}."
            ),
            "contacts": [],
        }

    domain = resolution.domain
    # --------------------------------------------------------
    # Hunter + contact relevance
    # --------------------------------------------------------

    database = JobDatabase()

    hunter = HunterClient()

    contact_store = ContactStore(
        database
    )

    relevance = ContactRelevanceAnalyzer()

    discovery = ContactDiscovery(
        hunter_client=hunter,
        contact_store=contact_store,
        relevance_analyzer=relevance,
    )

    matched_skills = parse_matched_skills(
        job
    )

    result = discovery.discover_for_job(
        company=company,
        company_domain=domain,
        canonical_role=(
            job.get(
                "canonical_role"
            )
            or "Business Analyst"
        ),
        matched_skills=matched_skills,
        limit=10,
        max_contacts=5,
        minimum_score=25,
    )

    return result

# ============================================================
# OUTREACH DRAFT
# ============================================================


def generate_draft(
    job: dict[str, Any],
    contact: dict[str, Any],
):

    profile = load_candidate_profile()

    generator = OutreachGenerator(
        candidate_profile=profile
    )

    return generator.generate(
        job=job,
        contact=contact,
    )


# ============================================================
# SEND APPROVED EMAIL
# ============================================================


def approve_and_send(
    run_id: str,
) -> dict[str, Any]:

    tracker = OutreachTracker()

    tracker.update_status(
        run_id,
        "APPROVED",
    )

    processor = ApprovalProcessor(
        tracker=tracker
    )

    return processor.process(
        run_id
    )


# ============================================================
# HEADER
# ============================================================

st.title(
    "🎯 JobPilot"
)

st.caption(
    "Live international job discovery "
    "and controlled candidate outreach"
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header(
        "JobPilot"
    )

    st.write(
        "Live job discovery → "
        "contact discovery → "
        "personalized outreach → "
        "manual approval → Gmail"
    )

    st.divider()

    st.write(
        "**Current CV**"
    )

    current_cv = (
        PROJECT_ROOT
        / "data"
        / "candidate"
        / "cv"
        / "current_cv.pdf"
    )

    if current_cv.exists():

        st.success(
            "Current CV available"
        )

        st.caption(
            str(current_cv)
        )

    else:

        st.warning(
            "Current CV not found."
        )


# ============================================================
# SECTION 1 — CV
# ============================================================

st.header(
    "1. Candidate Profile"
)

st.write(
    "Upload a newer CV if you want "
    "JobPilot to update the candidate profile."
)

uploaded_file = st.file_uploader(
    "Upload CV",
    type=[
        "pdf",
        "docx",
    ],
)

if uploaded_file is not None:

    st.success(
        f"Selected: {uploaded_file.name}"
    )

    if st.button(
        "Analyze CV",
        type="secondary",
    ):

        suffix = (
            Path(
                uploaded_file.name
            ).suffix.lower()
        )

        temp_path = None

        try:

            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=suffix,
            ) as temp_file:

                temp_file.write(
                    uploaded_file.getbuffer()
                )

                temp_path = Path(
                    temp_file.name
                )

            with st.spinner(
                "Analyzing CV..."
            ):

                service = (
                    CVIngestionService()
                )

                profile = service.ingest(
                    temp_path
                )

            st.success(
                "CV analyzed successfully."
            )

            col1, col2 = st.columns(2)

            with col1:

                st.metric(
                    "Profile Version",
                    profile.get(
                        "profile_version",
                        "N/A",
                    ),
                )

            with col2:

                st.metric(
                    "Source CV",
                    profile.get(
                        "source_cv",
                        "N/A",
                    ),
                )

            capabilities = profile.get(
                "capabilities",
                {},
            )

            st.subheader(
                "Detected Capabilities"
            )

            for category, values in (
                capabilities.items()
            ):

                st.markdown(
                    f"**{category.replace('_', ' ').title()}**"
                )

                if values:

                    st.write(
                        ", ".join(values)
                    )

                else:

                    st.write(
                        "None detected"
                    )

            evidence = profile.get(
                "capability_evidence",
                [],
            )

            if evidence:

                st.subheader(
                    "Capability Evidence"
                )

                for item in evidence:

                    with st.expander(
                        f"{item['name']} "
                        f"({item['evidence_strength']})"
                    ):

                        st.write(
                            f"**Category:** "
                            f"{item['category']}"
                        )

                        st.write(
                            "**Evidence:**"
                        )

                        for statement in item[
                            "evidence"
                        ]:

                            st.write(
                                f"- {statement}"
                            )

        except Exception as exc:

            st.error(
                f"CV analysis failed: {exc}"
            )

        finally:

            if (
                temp_path is not None
                and temp_path.exists()
            ):

                temp_path.unlink()


# ============================================================
# SECTION 2 — LIVE JOB SEARCH
# ============================================================

st.divider()

st.header(
    "2. Live Job Discovery"
)

st.write(
    "Search live sources, update SQLite, "
    "filter to recent jobs and score them "
    "against your candidate profile."
)

if st.button(
    "🔍 Run Live Job Search",
    type="primary",
    use_container_width=True,
):

    try:

        with st.spinner(
            "Running live job discovery..."
        ):

            report = (
                run_live_job_search()
            )

        st.success(
            "Live job search completed."
        )

        col1, col2, col3, col4, col5 = (
            st.columns(5)
        )

        with col1:

            st.metric(
                "Tasks",
                report[
                    "tasks_executed"
                ],
            )

        with col2:

            st.metric(
                "Discovered",
                report[
                    "jobs_discovered"
                ],
            )

        with col3:

            st.metric(
                "New",
                report[
                    "new_jobs"
                ],
            )

        with col4:

            st.metric(
                "Recent",
                report[
                    "recent_jobs"
                ],
            )

        with col5:

            st.metric(
                "BA Roles",
                report[
                    "ba_jobs"
                ],
            )

    except Exception as exc:

        st.error(
            f"Job search failed: {exc}"
        )


# ============================================================
# SECTION 3 — JOB RESULTS
# ============================================================

if st.session_state.search_completed:

    st.divider()

    st.header(
        "3. Newly Listed Business Analyst Jobs"
    )

    jobs = (
        st.session_state.recent_jobs
    )

    if not jobs:

        st.info(
            "No recent Business Analyst "
            "opportunities found."
        )

    else:

        st.caption(
            f"{len(jobs)} Business Analyst-title "
            f"opportunities found in the last 7 days."
        )

        for index, job in enumerate(
            jobs
        ):

            job_key = get_job_key(
                job
            )

            company = (
                job.get("company")
                or "Unknown Company"
            )

            title = (
                job.get("title")
                or "Business Analyst"
            )

            score = format_score(
                job.get(
                    "relevance_score"
                )
            )

            location = (
                job.get("location")
                or "Location not specified"
            )

            posted = (
                job.get("posted_date")
                or "Date unavailable"
            )

            level = (
                job.get(
                    "relevance_level"
                )
                or "N/A"
            )

            with st.container(
                border=True
            ):

                col1, col2, col3 = (
                    st.columns(
                        [5, 2, 2]
                    )
                )

                with col1:

                    st.subheader(
                        title
                    )

                    st.write(
                        f"**{company}**"
                    )

                    st.caption(
                        location
                    )

                with col2:

                    st.metric(
                        "Match Score",
                        score,
                    )

                    st.caption(
                        level
                    )

                with col3:

                    st.write(
                        f"**Posted:** {posted}"
                    )

                    source_url = (
                        job.get(
                            "source_url"
                        )
                    )

                    if source_url:

                        st.link_button(
                            "View Job",
                            source_url,
                        )

                description = (
                    job.get(
                        "description"
                    )
                    or ""
                )

                if description:

                    with st.expander(
                        "Job Description"
                    ):

                        st.write(
                            description
                        )

                # --------------------------------------------
                # Contact discovery
                # --------------------------------------------

                if st.button(
                    "👤 Find Potential Contacts",
                    key=(
                        f"contacts_"
                        f"{index}_"
                        f"{job_key}"
                    ),
                    use_container_width=True,
                ):

                    try:

                        with st.spinner(
                            f"Finding contacts at {company}..."
                        ):

                            result = (
                                discover_contacts(
                                    job
                                )
                            )

                        st.session_state.contacts[
                            job_key
                        ] = result

                        if result.get(
                            "contacts"
                        ):

                            st.success(
                                f"Found "
                                f"{len(result['contacts'])} "
                                f"potential contacts."
                            )

                        else:

                            st.warning(
                                result.get(
                                    "message",
                                    "No suitable contacts found.",
                                )
                            )

                    except Exception as exc:

                        st.error(
                            "Contact discovery failed: "
                            f"{exc}"
                        )

                # --------------------------------------------
                # Contacts
                # --------------------------------------------

                contact_result = (
                    st.session_state.contacts.get(
                        job_key
                    )
                )

                if contact_result:

                    contacts = (
                        contact_result.get(
                            "contacts",
                            [],
                        )
                    )

                    if contacts:

                        st.markdown(
                            "### Potential Reach"
                        )

                        for contact_index, contact in enumerate(
                            contacts
                        ):

                            contact_name = (
                                get_contact_name(
                                    contact
                                )
                            )

                            position = (
                                contact.get(
                                    "position"
                                )
                                or "Position unavailable"
                            )

                            email = (
                                contact.get(
                                    "email"
                                )
                                or "Email unavailable"
                            )

                            contact_key = (
                                f"{job_key}::"
                                f"{contact.get('email', '')}"
                            )

                            with st.container(
                                border=True
                            ):

                                left, right = (
                                    st.columns(
                                        [7, 3]
                                    )
                                )

                                with left:

                                    st.markdown(
                                        f"**{contact_name}**"
                                    )

                                    st.write(
                                        position
                                    )

                                    st.caption(
                                        email
                                    )

                                    if contact.get(
                                        "score"
                                    ) is not None:

                                        st.caption(
                                            "Contact relevance: "
                                            f"{contact.get('score')}"
                                        )

                                with right:

                                    # --------------------------------
                                    # Generate email
                                    # --------------------------------

                                    if st.button(
                                        "✉️ Generate Email",
                                        key=(
                                            f"draft_"
                                            f"{contact_index}_"
                                            f"{job_key}"
                                        ),
                                        use_container_width=True,
                                    ):

                                        try:

                                            with st.spinner(
                                                "Generating draft..."
                                            ):

                                                draft = (
                                                    generate_draft(
                                                        job,
                                                        contact,
                                                    )
                                                )

                                            profile = load_candidate_profile()

                                            tracker = (
                                                OutreachTracker()
                                            )

                                            record_result = (
                                                tracker.record(
                                                    message=draft,
                                                    job=job,
                                                    contact=contact,
                                                )
                                            )

                                            run_id = (
                                                record_result[
                                                    "run_id"
                                                ]
                                            )

                                            st.session_state.drafts[
                                                contact_key
                                            ] = {
                                                "draft": draft,
                                                "run_id": run_id,
                                            }

                                            st.success(
                                                f"Draft created: "
                                                f"{run_id}"
                                            )

                                        except Exception as exc:

                                            st.error(
                                                "Draft generation failed: "
                                                f"{exc}"
                                            )

                                # --------------------------------
                                # Existing draft
                                # --------------------------------

                                draft_data = (
                                    st.session_state.drafts.get(
                                        contact_key
                                    )
                                )

                                if draft_data:

                                    draft = (
                                        draft_data[
                                            "draft"
                                        ]
                                    )

                                    run_id = (
                                        draft_data[
                                            "run_id"
                                        ]
                                    )

                                    st.markdown(
                                        "---"
                                    )

                                    st.markdown(
                                        f"**Draft — {run_id}**"
                                    )

                                    st.text_input(
                                        "Subject",
                                        value=draft.subject,
                                        disabled=True,
                                        key=(
                                            f"subject_"
                                            f"{contact_index}_"
                                            f"{job_key}"
                                        ),
                                    )

                                    st.text_area(
                                        "Email",
                                        value=draft.body,
                                        height=260,
                                        disabled=True,
                                        key=(
                                            f"body_"
                                            f"{contact_index}_"
                                            f"{job_key}"
                                        ),
                                    )

                                    st.caption(
                                        f"CV attachment: "
                                        f"{draft.cv_path}"
                                    )

                                    send_result = (
                                        st.session_state.send_results.get(
                                            run_id
                                        )
                                    )

                                    if send_result:

                                        if (
                                            send_result.get(
                                                "status"
                                            )
                                            == "SENT"
                                        ):

                                            st.success(
                                                "✓ Email sent successfully."
                                            )

                                            if send_result.get(
                                                "gmail_message_id"
                                            ):

                                                st.caption(
                                                    "Gmail Message ID: "
                                                    f"{send_result['gmail_message_id']}"
                                                )

                                        else:

                                            st.error(
                                                str(
                                                    send_result
                                                )
                                            )

                                    else:

                                        # --------------------------------
                                        # EXPLICIT SEND APPROVAL
                                        # --------------------------------

                                        if st.button(
                                            "✅ Approve & Send",
                                            key=(
                                                f"send_"
                                                f"{contact_index}_"
                                                f"{job_key}"
                                            ),
                                            type="primary",
                                            use_container_width=True,
                                        ):

                                            try:

                                                with st.spinner(
                                                    "Sending approved email..."
                                                ):

                                                    result = (
                                                        approve_and_send(
                                                            run_id
                                                        )
                                                    )

                                                st.session_state.send_results[
                                                    run_id
                                                ] = result

                                                if (
                                                    result.get(
                                                        "status"
                                                    )
                                                    == "SENT"
                                                ):

                                                    st.success(
                                                        "✓ Email sent successfully."
                                                    )

                                                    if result.get(
                                                        "gmail_message_id"
                                                    ):

                                                        st.caption(
                                                            "Gmail Message ID: "
                                                            f"{result['gmail_message_id']}"
                                                        )

                                                else:

                                                    st.warning(
                                                        result
                                                    )

                                            except Exception as exc:

                                                st.session_state.send_results[
                                                    run_id
                                                ] = {
                                                    "status": "ERROR",
                                                    "error": str(
                                                        exc
                                                    ),
                                                }

                                                st.error(
                                                    "Email send failed: "
                                                    f"{exc}"
                                                )