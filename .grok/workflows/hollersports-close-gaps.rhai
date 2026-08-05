// HollerSports: close remaining engineering gaps (advisory only — no money).
// Fixed work-list (deterministic). Fan-out implementers, then verify with tests.

let meta = #{
    name: "hollersports-close-gaps",
    description: "Close HollerSports P1/P5 gaps: multi-event free-first, multi-sport ESPN, schema hygiene, version bump; verify with pytest",
    when_to_use: "After advisory beta, to close free-first multi-event join, multi-sport ESPN, LIVE_APPROVED enum strip, package version 0.3.0",
    phases: [
        #{ title: "Implement", detail: "parallel gap closers (advisory-only product law)" },
        #{ title: "Verify", detail: "pytest + smoke fail-closed" },
        #{ title: "Report", detail: "scratch summary" },
    ],
};

let done_schema = #{
    "type": "object",
    "required": ["summary", "success", "files_changed"],
    "properties": #{
        "summary": #{ "type": "string" },
        "success": #{ "type": "boolean" },
        "files_changed": #{
            "type": "array",
            "items": #{ "type": "string" },
            "maxItems": 40,
        },
        "notes": #{ "type": "string" },
    },
};

let verify_schema = #{
    "type": "object",
    "required": ["ok", "pytest_summary", "evidence"],
    "properties": #{
        "ok": #{ "type": "boolean" },
        "pytest_summary": #{ "type": "string" },
        "evidence": #{ "type": "string" },
        "failures": #{ "type": "string" },
    },
};

// Optional args.repo_root — default Hollersports home path for this machine.
let repo = if args == () { () } else { args.repo_root };
if repo == () {
    repo = "/home/scrimshawlife/Hollersports";
}

// --- Product law injected into every implementer ---
let law = "";
law += "PRODUCT LAW (non-negotiable): HollerSports is betting ADVISORY only. ";
law += "Never handle real money, place book tickets, or set capital_authority/execution_authority true. ";
law += "Paper stakes/ROI are simulation metrics for advice quality only. ";
law += "Repo root: " + repo + ". Work on branch main. Use tools (read_file, search_replace, run_terminal_command). ";
law += "TDD where practical. Commit with a clear message when done. ";

phase("Implement");
log("Launching 4 gap-closer agents (budget ~5 total with verify)");

let jobs = [];

// Job 1: multi-event free-first + team-based join
let p1 = "";
p1 += law;
p1 += "TASK: Multi-event free-first observation pack and team-based event join. ";
p1 += "Read packages/hollersports/hollersports/sources/free_first_ingest.py, source_conflict.py, fixture_adapter.py, pipelines/operator_day.py. ";
p1 += "1) Improve detect_event_conflicts or add join_events_by_teams() that matches events across ESPN and Odds by normalized team set + start_time proximity (not only event_id equality). ";
p1 += "2) Change build_live_observation_pack so ingest is not limited to primary[0] only: either emit multi-event markets merged into one MarketIngestionPacket when schema allows, OR produce a list of ingest payloads and document the helper run_multi_event_ingest. Prefer multi-market on a slate packet with multiple events if MarketIngestionPacket is single-event — then add free_first_to_operator_inputs() returning list of ingest payloads. ";
p1 += "3) Add unit tests with injected ESPN+odds raw multi-game fixtures (no network). ";
p1 += "4) pytest the new tests then full tests/ --ignore=hollersports-core. Commit. ";
p1 += "Return JSON summary of files_changed and success.";
jobs.push(#{
    prompt: p1,
    label: "gap:multi-event-join",
    capability_mode: "all",
    output_schema: done_schema,
});

// Job 2: multi-sport ESPN
let p2 = "";
p2 += law;
p2 += "TASK: Multi-sport ESPN scoreboard endpoints (day-one leagues). ";
p2 += "Read packages/hollersports/hollersports/sources/espn_scoreboard.py and tests/unit/test_espn_scoreboard.py. ";
p2 += "1) Add league→ESPN path map for NBA, NFL, MLB, NHL, and soccer (MLS and/or EPL). ";
p2 += "2) fetch_espn_scoreboard(league=...) / normalize with league param. Keep fetch_espn_nba_scoreboard as thin wrapper. ";
p2 += "3) Unit tests for normalize for at least 2 sports using minimal raw fixtures (no live network required in CI). ";
p2 += "4) pytest those tests + full suite ignore hollersports-core. Commit. ";
p2 += "Return JSON summary.";
jobs.push(#{
    prompt: p2,
    label: "gap:multi-sport-espn",
    capability_mode: "all",
    output_schema: done_schema,
});

// Job 3: schema hygiene LIVE_APPROVED + package version 0.3.0
let p3 = "";
p3 += law;
p3 += "TASK: Schema hygiene and version alignment. ";
p3 += "1) Remove or forbid LIVE_APPROVED as a constructible execution mode for v1: update schemas/json/ExecutionPacket.v1.schema.json and hollersports/schemas/packets.py so mode is PAPER_ONLY | MANUAL_REVIEW | LIVE_DISABLED only (drop LIVE_APPROVED from enum). Keep assert_no_live_capital defense. Update any tests that reference LIVE_APPROVED as allowed. Do not add a money path. ";
p3 += "2) Bump packages/hollersports/pyproject.toml version to 0.3.0 to match tag v0.3.0-advisory-beta. Update README badge if it still says 0.2.0. ";
p3 += "3) pytest full suite --ignore=hollersports-core. Commit. Return JSON summary.";
jobs.push(#{
    prompt: p3,
    label: "gap:schema-version",
    capability_mode: "all",
    output_schema: done_schema,
});

// Job 4: API authority errors as 4xx + paper gates respect source health when not fixture
let p4 = "";
p4 += law;
p4 += "TASK: API hygiene for advisory operator. ";
p4 += "Read packages/hollersports/hollersports/api/routes.py and deps.py. ";
p4 += "1) Convert authority/live-mode ValueError from _safe_packet into HTTPException 403 with clear detail (still fail-closed). ";
p4 += "2) When ingest source_health status is FAIL, do not hardcode all paper gates True on subsequent paper for that run if store has failed health — set source_health_gate False so paper rejects. Fixture full-day may still use open gates only inside operator_day. ";
p4 += "3) Add a focused TestClient test for 403 if you can trigger safely without breaking happy path. ";
p4 += "4) pytest full suite. Commit. Return JSON summary.";
jobs.push(#{
    prompt: p4,
    label: "gap:api-hygiene",
    capability_mode: "all",
    output_schema: done_schema,
});

let impl_results = parallel(jobs);

let impl_ok = 0;
let impl_fail = 0;
let all_files = [];
let notes = "";
for r in impl_results {
    if r == () || !r.success {
        impl_fail += 1;
        notes += "implementer failed or empty; ";
    } else if r.output.success == true {
        impl_ok += 1;
        if r.output.files_changed != () {
            for f in r.output.files_changed {
                all_files.push(f);
            }
        }
        if r.output.notes != () {
            notes += r.output.notes + "; ";
        }
    } else {
        impl_fail += 1;
        if r.output.summary != () {
            notes += r.output.summary + "; ";
        }
    }
}
log("Implementers ok=" + impl_ok.to_string() + " fail=" + impl_fail.to_string());

phase("Verify");
let vp = "";
vp += law;
vp += "TASK: Verification gate for HollerSports close-gaps run. ";
vp += "cd " + repo + " and run: pytest tests/ --ignore=hollersports-core -q ";
vp += "Also run: python scripts/smoke_operator_day.py --out docs/evidence/smoke_operator_day.last.json ";
vp += "Use run_terminal_command and capture real output. ";
vp += "Set ok=true only if pytest is fully green (all passed, 0 failed). ";
vp += "Put the pytest last line in pytest_summary and key evidence in evidence. ";
vp += "If failures, ok=false and put tail of failures in failures field.";
let v = agent(vp, #{
    label: "verify:pytest-smoke",
    capability_mode: "execute",
    output_schema: verify_schema,
});

let verified = false;
let pytest_summary = "NOT_RUN";
let evidence = "";
let failures = "";
if v != () && v.success && v.output.ok != () {
    verified = v.output.ok == true;
    if v.output.pytest_summary != () { pytest_summary = v.output.pytest_summary; }
    if v.output.evidence != () { evidence = v.output.evidence; }
    if v.output.failures != () { failures = v.output.failures; }
}

phase("Report");
let report = "";
report += "# HollerSports close-gaps workflow report\n\n";
report += "Product: advisory only (no real money).\n\n";
report += "## Implement\n";
report += "- ok: " + impl_ok.to_string() + "\n";
report += "- fail: " + impl_fail.to_string() + "\n";
report += "- notes: " + notes + "\n\n";
report += "## Verify\n";
report += "- verified: " + verified.to_string() + "\n";
report += "- pytest_summary: " + pytest_summary + "\n";
report += "- evidence: " + evidence + "\n";
if failures != "" {
    report += "- failures: " + failures + "\n";
}
report += "\n## Files (reported)\n";
for f in all_files {
    report += "- " + f + "\n";
}

let path = write_scratch_file("close-gaps-report.md", report);

// Fail closed: verification must pass for complete success semantics in value.
if !verified {
    complete(#{
        summary: "Gaps partially applied but verification failed",
        path: path,
        verified: false,
        implementers_ok: impl_ok,
        implementers_fail: impl_fail,
        pytest_summary: pytest_summary,
        failures: failures,
    });
}

complete(#{
    summary: "Close-gaps complete; pytest green",
    path: path,
    verified: true,
    implementers_ok: impl_ok,
    implementers_fail: impl_fail,
    pytest_summary: pytest_summary,
    files_changed: all_files,
});
