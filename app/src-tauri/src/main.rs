// Alias Studio desktop shell. The pipeline is a Python sidecar speaking JSONL
// on stdout (`publikclip --jsonl ...`); this shell spawns it, forwards every
// event to the frontend, and exposes small filesystem/settings commands.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::fs;
use std::io::{BufRead, BufReader};
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::sync::Mutex;

use serde_json::{json, Value};
use tauri::{AppHandle, Emitter, Manager};

fn home_dir() -> PathBuf {
    if let Ok(custom) = std::env::var("PUBLIKCLIP_HOME") {
        return PathBuf::from(custom);
    }
    dirs_home().join(".publikclip")
}

fn dirs_home() -> PathBuf {
    // HOME on Unix; Windows services and some launch paths only set USERPROFILE.
    std::env::var_os("HOME")
        .or_else(|| std::env::var_os("USERPROFILE"))
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("/"))
}

/// Command that never flashes a console window on Windows (CREATE_NO_WINDOW).
/// Every pipeline/tool spawn goes through this — a GUI app popping cmd.exe
/// windows for each sidecar call reads as malware to most people.
///
/// Also forces Python's UTF-8 mode (PEP 540): without it, `open()`/
/// `Path.write_text()` calls in the pipeline that don't pass an explicit
/// `encoding=` fall back to the OS locale encoding — cp1252 on a typical
/// Windows install, not UTF-8. Any non-ASCII character written that way
/// (an "±" in a scoring rubric string, in this case) becomes an invalid
/// byte sequence on disk that Rust's own strict UTF-8 file reads then
/// silently fail on, dropping that whole checkpoint as null with no error
/// surfaced anywhere. uv/curl and friends ignore the extra env var.
fn quiet_command(program: &str) -> Command {
    #[allow(unused_mut)]
    let mut cmd = Command::new(program);
    cmd.env("PYTHONUTF8", "1");
    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
    }
    cmd
}

// ---------------------------------------------------------------------------
// T-07 cancellation. Three facts drive this shape:
//
//   - The sidecar is a tree (uv -> python -> ffmpeg); on Windows, killing the
//     direct child leaves its descendants encoding at full CPU. A Job Object
//     kills the whole tree atomically, and membership is inherited at process
//     creation, so an ffmpeg spawned a millisecond after adoption is already
//     a member - taskkill /T's pid-snapshot race has no equivalent here.
//   - KILL_ON_JOB_CLOSE is deliberately NOT set: quitting the app mid-job
//     leaves the pipeline finishing headless, exactly as before this task.
//     Changing that is an E2-F05 decision, not a cancel side effect.
//   - Two sentinel files in the job dir are shared with python, with split
//     ownership (jobs/queue.py carries the matching comment - do not "tidy"
//     one half): cancel.requested is written here and consumed by run_stages
//     at a stage boundary; the cancelled marker is written here right after a
//     hard kill so the library (list_job_dirs reads the filesystem, not
//     SQLite) is correct even if the bookkeeping one-shot never runs. Python
//     writes the same marker at a boundary cancel and deletes both files
//     when a run starts.

const CANCEL_FLAG: &str = "cancel.requested";
const CANCELLED_MARKER: &str = "cancelled";

#[cfg(target_os = "windows")]
mod job_object {
    use windows_sys::Win32::Foundation::{CloseHandle, HANDLE};
    use windows_sys::Win32::System::JobObjects::{
        AssignProcessToJobObject, CreateJobObjectW, TerminateJobObject,
    };

    pub struct JobHandle(HANDLE);
    // A job object handle is process-global; moving it across threads is fine.
    unsafe impl Send for JobHandle {}

    impl JobHandle {
        /// Create a job and put `child` - and every future descendant - in
        /// it. Adoption happens right after spawn(), long before uv gets to
        /// exec python, and descendants are members from creation onward.
        pub fn adopt(child: &std::process::Child) -> Option<Self> {
            use std::os::windows::io::AsRawHandle;
            unsafe {
                let job = CreateJobObjectW(std::ptr::null(), std::ptr::null());
                if job.is_null() {
                    return None;
                }
                if AssignProcessToJobObject(job, child.as_raw_handle() as HANDLE) == 0 {
                    CloseHandle(job);
                    return None;
                }
                Some(Self(job))
            }
        }

        pub fn terminate(&self) {
            unsafe {
                TerminateJobObject(self.0, 1);
            }
        }
    }

    impl Drop for JobHandle {
        fn drop(&mut self) {
            unsafe {
                CloseHandle(self.0);
            }
        }
    }
}

struct ActiveRun {
    job_id: String, // every start path knows its id at spawn (T-08)
    child_pid: u32,
    cancel_requested: bool,
    #[cfg(target_os = "windows")]
    job: Option<job_object::JobHandle>, // None: adoption failed -> taskkill fallback
}

/// Everything the queue's Rust side may decide with, under ONE mutex so
/// idle-check, latch and pause are a single critical section (T-08).
struct QueueState {
    active: Option<ActiveRun>,
    /// Cancel pressed while nothing was (visibly) running - which includes
    /// the window between a run's take() and the auto-advance spawning the
    /// next job. Recorded intent: the next auto-advance consumes it and
    /// holds; every explicit go gesture clears it first. Session-scoped by
    /// construction, and a running job implies it is clear, because every
    /// start path consumed or cleared it.
    cancel_latch: bool,
    /// "Pause after the current job" - consulted by the auto-advance only.
    paused: bool,
}

struct RunState(Mutex<QueueState>);

/// Which kind of sidecar stream_pipeline is driving. Only full job runs
/// register in RunState - edit renders are never cancellable from here.
#[derive(Clone, Copy, PartialEq)]
enum PipelineKind {
    Job,
    Tool,
}

/// Cancel the running job: sentinel files first (a python that survives the
/// kill still stops at its next boundary, and the library marker exists even
/// if every later step fails), then kill the whole tree. Bookkeeping happens
/// in stream_pipeline once wait() returns.
#[tauri::command]
fn cancel_job(state: tauri::State<RunState>) -> Result<(), String> {
    let mut guard = state.0.lock().unwrap();
    let Some(run) = guard.active.as_mut() else {
        // Nothing to kill - but the press still means "and start nothing".
        // Without this latch, a Cancel landing in the take()->advance
        // window would error out here and then watch the next job start.
        guard.cancel_latch = true;
        return Ok(());
    };
    run.cancel_requested = true;
    {
        let dir = home_dir().join("jobs").join(&run.job_id);
        let _ = fs::write(dir.join(CANCEL_FLAG), "1");
        let _ = fs::write(dir.join(CANCELLED_MARKER), "1");
    }
    #[cfg(target_os = "windows")]
    {
        match &run.job {
            Some(job) => job.terminate(),
            None => {
                // Job-object adoption failed at spawn; degrade to the pid
                // walk. It has the snapshot race the job object doesn't -
                // the flag file above is the belt for exactly that race.
                let _ = quiet_command("taskkill")
                    .args(["/T", "/F", "/PID", &run.child_pid.to_string()])
                    .output();
            }
        }
    }
    #[cfg(unix)]
    {
        // UNVERIFIED on real macOS until T-19 lands: process_group(0) at
        // spawn makes the child's pid its pgid, so this reaches the tree.
        unsafe {
            libc::killpg(run.child_pid as i32, libc::SIGKILL);
        }
    }
    Ok(())
}

/// After a cancel, once the child is dead: run the bookkeeping one-shot,
/// reconcile the optimistic marker, and emit at most one 'cancelled' event.
/// The boundary path (python saw the flag between stages) exits 0 having
/// emitted its own 'cancelled' through the JSONL stream, so this emits only
/// for non-zero exits - one event either way.
fn handle_cancelled_exit(
    app: &AppHandle,
    run: &ActiveRun,
    exit: Option<&std::process::ExitStatus>,
) {
    let clean_exit = exit.map(|s| s.success()).unwrap_or(false);
    let status_after = one_shot_json(&[
        "jobs".to_string(),
        "mark-cancelled".to_string(),
        run.job_id.clone(),
    ])
    .and_then(|v| v["status"].as_str().map(String::from));
    // The cancel raced the job's own completion: nothing was cancelled,
    // so take back the marker cancel_job optimistically wrote.
    if clean_exit && status_after.as_deref() == Some("done") {
        let _ = fs::remove_file(home_dir().join("jobs").join(&run.job_id).join(CANCELLED_MARKER));
    }
    if !clean_exit {
        let _ = app.emit(
            "pipeline-event",
            json!({"event": "cancelled", "job_id": run.job_id.clone()}),
        );
    }
}

/// Where the Python pipeline lives and how to invoke it.
/// Dev builds call `uv run` against the repo's pipeline/ directory. Packaged
/// builds invoke the bundled python env (M6); resolution stays in one place.
fn pipeline_invocation() -> (String, Vec<String>) {
    if cfg!(debug_assertions) {
        let pipeline_dir: PathBuf = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../../pipeline")
            .canonicalize()
            .unwrap_or_else(|_| PathBuf::from("../pipeline"));
        (
            "uv".to_string(),
            vec![
                "--directory".to_string(),
                pipeline_dir.to_string_lossy().to_string(),
                "run".to_string(),
                "publikclip".to_string(),
            ],
        )
    } else {
        // Packaged: bundled uv + pipeline source under the platform's
        // resource layout — macOS keeps them in the .app's Resources dir,
        // Windows (NSIS) lands them in resources\ next to the exe. The venv
        // bootstraps into PUBLIKCLIP_HOME on first run (uv handles Python
        // 3.12 download + deps; the onboarding screen owns expectations).
        let exe_dir = std::env::current_exe()
            .ok()
            .and_then(|p| p.parent().map(|d| d.to_path_buf()))
            .unwrap_or_else(|| PathBuf::from("."));
        let resources = if cfg!(target_os = "macos") {
            exe_dir.join("../Resources/resources")
        } else {
            exe_dir.join("resources")
        };
        let uv = if cfg!(target_os = "windows") { "bin/uv.exe" } else { "bin/uv" };
        (
            resources.join(uv).to_string_lossy().to_string(),
            vec![
                "--directory".to_string(),
                resources.join("pipeline").to_string_lossy().to_string(),
                "run".to_string(),
                "publikclip".to_string(),
            ],
        )
    }
}

#[tauri::command]
fn resume_job(
    app: AppHandle,
    job_id: String,
    llm: Option<String>,
    captions: Option<String>,
    camera: Option<String>,
    gameplay_amount: Option<f64>,
) -> Result<(), String> {
    let mut args = vec!["--jsonl".to_string(), "resume".to_string(), job_id.clone()];
    if let Some(mode) = llm {
        args.push("--llm".to_string());
        args.push(mode);
    }
    if let Some(preset) = captions {
        args.push("--captions".to_string());
        args.push(preset);
    }
    if let Some(cam) = camera {
        args.push("--camera".to_string());
        args.push(cam);
    }
    if let Some(g) = gameplay_amount {
        args.push("--gameplay-amount".to_string());
        args.push(g.to_string());
    }
    {
        let state = app.state::<RunState>();
        let mut guard = state.0.lock().unwrap();
        if guard.active.is_some() {
            return Err("a job is already running".to_string());
        }
        guard.cancel_latch = false; // an explicit go gesture outranks a stale latch
        start_job_locked(&app, &mut guard, args, job_id)?;
    }
    // Outside the lock block: emit_queue_state takes the RunState lock.
    emit_queue_state(&app);
    Ok(())
}

/// Run one CLI verb to completion; every JSON line it printed, in order.
fn one_shot_json_lines(extra: &[String]) -> Vec<Value> {
    let (program, base_args) = pipeline_invocation();
    let mut args = base_args;
    args.extend_from_slice(extra);
    match quiet_command(&program).args(&args).output() {
        Ok(out) => String::from_utf8_lossy(&out.stdout)
            .lines()
            .filter_map(|l| serde_json::from_str::<Value>(l.trim()).ok())
            .collect(),
        Err(_) => vec![],
    }
}

/// Run one CLI verb to completion; its last JSON line.
fn one_shot_json(extra: &[String]) -> Option<Value> {
    one_shot_json_lines(extra).pop()
}

/// The queue view used to poll queue_state on a 2s timer, and every call
/// spawned a `uv run` subprocess that can take seconds (uv re-syncs the env
/// per launch), so polls stacked up faster than they answered. The fix is
/// push, not poll: this caches python's `--jsonl jobs` answer VERBATIM —
/// no derived state, no decisions, SQLite (through python) stays the only
/// truth — and it is invalidated by overwrite at exactly the moments the
/// shell changes the queue or learns it changed: enqueue, advance, job
/// exit, cancel-pending, startup reconcile. Each landed answer is emitted
/// as a `queue-state` event. `gen` discards an answer overtaken by a newer
/// ask, so the cache only ever moves forward.
struct QueueCache(Mutex<QueueCacheInner>);
struct QueueCacheInner {
    gen: u64,
    jobs: Option<Vec<Value>>,
}

/// The queue-state payload: the cached jobs listing plus the shell's own
/// session truth (paused, active job). `ready: false` means the cache is
/// still cold — the frontend renders "loading", not a false "empty".
/// Never call while holding the RunState lock: it takes that lock itself.
fn queue_snapshot(app: &AppHandle) -> Value {
    let (jobs, ready) = {
        let cache = app.state::<QueueCache>();
        let guard = cache.0.lock().unwrap();
        match &guard.jobs {
            Some(jobs) => (jobs.clone(), true),
            None => (Vec::new(), false),
        }
    };
    let (paused, active_job_id) = {
        let state = app.state::<RunState>();
        let guard = state.0.lock().unwrap();
        (guard.paused, guard.active.as_ref().map(|r| r.job_id.clone()))
    };
    json!({"jobs": jobs, "paused": paused, "active_job_id": active_job_id, "ready": ready})
}

fn emit_queue_state(app: &AppHandle) {
    let _ = app.emit("queue-state", queue_snapshot(app));
}

/// Re-ask python for the jobs listing off-thread, store the answer, push
/// it to the frontend. Only ever called at mutation moments — never on a
/// timer — so there is no process pileup to have.
fn refresh_queue_cache(app: &AppHandle) {
    let my_gen = {
        let cache = app.state::<QueueCache>();
        let mut guard = cache.0.lock().unwrap();
        guard.gen += 1;
        guard.gen
    };
    let app = app.clone();
    std::thread::spawn(move || {
        let jobs = one_shot_json_lines(&["--jsonl".to_string(), "jobs".to_string()]);
        {
            let cache = app.state::<QueueCache>();
            let mut guard = cache.0.lock().unwrap();
            if guard.gen != my_gen {
                return; // overtaken by a newer ask; its answer wins
            }
            guard.jobs = Some(jobs);
        }
        emit_queue_state(&app);
    });
}

/// Spawn a job run and register it as the active run. The caller holds the
/// QueueState lock and this function registers before returning: idle-check,
/// spawn and registration must be one atomic step, or two advance callers
/// (an exit hook and an enqueue) could both pass the idle check and
/// double-spawn - which would also leave one of them outside RunState,
/// unreachable by cancel.
fn start_job_locked(
    app: &AppHandle,
    qs: &mut QueueState,
    args: Vec<String>,
    job_id: String,
) -> Result<(), String> {
    let (program, base_args) = pipeline_invocation();
    let mut full = base_args;
    full.extend(args);
    let mut cmd = quiet_command(&program);
    cmd.args(&full).stdout(Stdio::piped()).stderr(Stdio::piped());
    // Its own process group on unix is what lets cancel_job killpg the
    // whole tree. UNVERIFIED on real macOS until T-19 lands.
    #[cfg(unix)]
    {
        use std::os::unix::process::CommandExt;
        cmd.process_group(0);
    }
    let child = cmd
        .spawn()
        .map_err(|err| format!("could not start pipeline: {err}"))?;
    #[cfg(target_os = "windows")]
    let job = job_object::JobHandle::adopt(&child);
    qs.active = Some(ActiveRun {
        job_id,
        child_pid: child.id(),
        cancel_requested: false,
        #[cfg(target_os = "windows")]
        job,
    });
    let app = app.clone();
    std::thread::spawn(move || stream_child(&app, child, PipelineKind::Job));
    Ok(())
}

/// Spawn a non-job sidecar stream (edit render). Never registers in
/// RunState, so cancel cannot reach it - deliberately.
fn spawn_tool(app: &AppHandle, args: Vec<String>) {
    let (program, base_args) = pipeline_invocation();
    let mut full = base_args;
    full.extend(args);
    let app = app.clone();
    std::thread::spawn(move || {
        let spawned = quiet_command(&program)
            .args(&full)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn();
        match spawned {
            Ok(child) => stream_child(&app, child, PipelineKind::Tool),
            Err(err) => {
                let _ = app.emit(
                    "pipeline-event",
                    json!({"event": "result", "ok": false, "error": format!("could not start pipeline: {err}")}),
                );
            }
        }
    });
}

/// The queue's only Rust-side logic: when idle, ask python what is next and
/// spawn it. Policy - order, eligibility, what failure means for the rest -
/// lives entirely in next_pending() on the python side. The one judgment
/// here is which gestures reach this function at all: completion and crash
/// auto-advance; cancel and app launch do not (gesture semantics, the same
/// class as the cancelled-vs-exited routing above).
///
/// The QueueState lock deliberately spans the `jobs next` one-shot:
/// ask-first-lock-after would let two concurrent advances receive the same
/// job id and double-spawn it. The cost is that cancel_job can block for
/// about a second - only ever while nothing is running, when there is
/// nothing to cancel. Do not "optimise" this into the broken ordering.
fn try_advance(app: &AppHandle, explicit: bool) {
    let state = app.state::<RunState>();
    let mut guard = state.0.lock().unwrap();
    if guard.active.is_some() {
        return;
    }
    if explicit {
        guard.cancel_latch = false; // a deliberate go outranks a stale latch
    } else {
        if guard.paused {
            return;
        }
        if guard.cancel_latch {
            // A Cancel press landed in the take()->advance window. Consume
            // it and hold: "the user pressed Cancel and a job started" is
            // the one behaviour this design promises never to produce.
            guard.cancel_latch = false;
            return;
        }
    }
    let next = one_shot_json(&["jobs".to_string(), "next".to_string()])
        .and_then(|v| v["job_id"].as_str().map(String::from));
    let Some(id) = next else { return };
    let args = vec!["--jsonl".to_string(), "resume".to_string(), id.clone()];
    // A spawn failure leaves the job pending; the next explicit gesture
    // retries it rather than anything looping here.
    let _ = start_job_locked(app, &mut guard, args, id);
}

fn stream_child(app: &AppHandle, mut child: std::process::Child, kind: PipelineKind) {
    // Keep the tail of stderr around so a non-zero exit can report *why* —
    // the sidecar's traceback lands here, not in the JSONL stream on stdout.
    let stderr_tail = std::sync::Arc::new(std::sync::Mutex::new(String::new()));
    let stderr_thread = child.stderr.take().map(|stderr| {
        let tail = stderr_tail.clone();
        std::thread::spawn(move || {
            for line in BufReader::new(stderr).lines().map_while(Result::ok) {
                let mut buf = tail.lock().unwrap();
                buf.push_str(&line);
                buf.push('\n');
                let excess = buf.len().saturating_sub(4000);
                if excess > 0 {
                    buf.replace_range(0..excess, "");
                }
            }
        })
    });
    if let Some(stdout) = child.stdout.take() {
        for line in BufReader::new(stdout).lines().map_while(Result::ok) {
            if let Ok(value) = serde_json::from_str::<Value>(&line) {
                let _ = app.emit("pipeline-event", value);
            }
        }
    }
    let status = child.wait();
    if let Some(t) = stderr_thread {
        let _ = t.join();
    }
    if kind == PipelineKind::Job {
        let finished = app.state::<RunState>().0.lock().unwrap().active.take();
        if let Some(run) = finished {
            if run.cancel_requested {
                handle_cancelled_exit(app, &run, status.as_ref().ok());
                // mark-cancelled has run by now; the listing knows.
                refresh_queue_cache(app);
                return; // deliberate stop: no crash event, and no auto-advance
            }
        }
    }
    if let Ok(status) = &status {
        if !status.success() {
            let detail = stderr_tail.lock().unwrap().trim().to_string();
            let _ = app.emit(
                "pipeline-event",
                json!({"event": "exited", "code": status.code(), "stderr": detail}),
            );
        }
    }
    if kind == PipelineKind::Job {
        // Completion or crash: the queue continues (one failure does not
        // stop the rest). A cancel returned above, so the queue holds.
        try_advance(app, false);
        // Emit now (active flipped), then re-ask so the terminal status
        // python just wrote lands in the cache.
        emit_queue_state(app);
        refresh_queue_cache(app);
    }
}

/// Enqueue: `jobs create` (the row exists before any run does), then let
/// the advance decide - enqueue-while-idle starts immediately, keeping the
/// current one-job feel; enqueue-while-busy just queues.
#[tauri::command]
async fn enqueue_job(
    app: AppHandle,
    source: String,
    llm: Option<String>,
    captions: Option<String>,
    gameplay_amount: Option<f64>,
) -> Result<String, String> {
    let mut args = vec!["jobs".to_string(), "create".to_string(), source];
    if let Some(mode) = llm {
        args.push("--llm".to_string());
        args.push(mode);
    }
    if let Some(preset) = captions {
        args.push("--captions".to_string());
        args.push(preset);
    }
    if let Some(g) = gameplay_amount {
        args.push("--gameplay-amount".to_string());
        args.push(g.to_string());
    }
    let created = one_shot_json(&args).ok_or_else(|| "enqueue produced no answer".to_string())?;
    let job_id = created["job_id"]
        .as_str()
        .ok_or_else(|| "enqueue returned no job id".to_string())?
        .to_string();
    try_advance(&app, true);
    // Emit first (the active flip is knowable now), then refresh so the
    // new row itself reaches the cache.
    emit_queue_state(&app);
    refresh_queue_cache(&app);
    Ok(job_id)
}

/// The explicit re-arm: after a cancel held the queue, or a fresh launch.
#[tauri::command]
async fn start_queue(app: AppHandle) -> Result<(), String> {
    try_advance(&app, true);
    emit_queue_state(&app);
    refresh_queue_cache(&app);
    Ok(())
}

#[tauri::command]
async fn set_queue_paused(app: AppHandle, paused: bool) -> Result<(), String> {
    {
        let state = app.state::<RunState>();
        state.0.lock().unwrap().paused = paused;
    }
    // Pause is shell session truth, not SQLite: no re-ask, just push.
    emit_queue_state(&app);
    Ok(())
}

/// Answered from the cache: opening the queue view must be instant and
/// must not spawn a process. A cold cache kicks one refresh, whose answer
/// arrives as a queue-state event.
#[tauri::command]
async fn queue_state(app: AppHandle) -> Result<Value, String> {
    let snapshot = queue_snapshot(&app);
    if snapshot["ready"] == Value::Bool(false) {
        refresh_queue_cache(&app);
    }
    Ok(snapshot)
}

#[tauri::command]
async fn cancel_pending_job(app: AppHandle, job_id: String) -> Result<Value, String> {
    let out = one_shot_json(&["jobs".to_string(), "cancel-pending".to_string(), job_id])
        .ok_or_else(|| "cancel-pending produced no answer".to_string())?;
    refresh_queue_cache(&app);
    Ok(out)
}

/// Everything the review UI needs for one job, read straight off the job
/// dir's checkpoint files (artifacts are the truth).
#[tauri::command]
fn job_results(job_id: String) -> Result<Value, String> {
    let dir = home_dir().join("jobs").join(&job_id);
    if !dir.exists() {
        return Err(format!("no job dir for {job_id}"));
    }
    let read_stage = |name: &str| -> Value {
        fs::read_to_string(dir.join(format!("{name}.json")))
            .ok()
            .and_then(|s| serde_json::from_str::<Value>(&s).ok())
            .and_then(|v| v.get("data").cloned())
            .unwrap_or(Value::Null)
    };
    Ok(json!({
        "job_id": job_id,
        "dir": dir.to_string_lossy(),
        "ingest": read_stage("ingest"),
        "score": read_stage("score"),
        "camera": read_stage("camera"),
        "render": read_stage("render"),
        "events": read_stage("events"),
        "candidates": read_stage("candidates"),
    }))
}

#[tauri::command]
fn list_job_dirs() -> Result<Vec<Value>, String> {
    let jobs_dir = home_dir().join("jobs");
    let mut out = vec![];
    if let Ok(entries) = fs::read_dir(&jobs_dir) {
        for entry in entries.flatten() {
            let id = entry.file_name().to_string_lossy().to_string();
            let dir = entry.path();
            let has_render = dir.join("render.json").exists();
            let has_ingest = dir.join("ingest.json").exists();
            let cancelled = dir.join(CANCELLED_MARKER).exists();
            let title = fs::read_to_string(dir.join("ingest.json"))
                .ok()
                .and_then(|s| serde_json::from_str::<Value>(&s).ok())
                .and_then(|v| v["data"]["title"].as_str().map(String::from));
            out.push(json!({
                "id": id, "title": title,
                "ingested": has_ingest, "rendered": has_render,
                "cancelled": cancelled,
            }));
        }
    }
    out.sort_by(|a, b| b["id"].as_str().cmp(&a["id"].as_str()));
    Ok(out)
}

/// One cheap authenticated call (ListModels) to learn a key's fate. Three
/// answers, not two:
///   - "verified": Google accepted the key (200; 429 also proves it is
///     recognized - a throttle is not a rejection)
///   - "rejected": Google affirmatively refused it (400/401/403; the API
///     answers 400 API_KEY_INVALID for a malformed key)
///   - "unverified": the check itself was impossible (no network, a 5xx,
///     curl missing). §5.9: inability to check must never become a wall.
/// §5.11: the key rides a header, and the header reaches curl through
/// stdin (`-H @-`), so it is never in a URL - and never in argv either.
fn gemini_key_status(key: &str) -> &'static str {
    use std::io::Write;
    let sink = if cfg!(target_os = "windows") { "NUL" } else { "/dev/null" };
    let spawned = quiet_command("curl")
        .args([
            "-s", "-m", "8", "-o", sink, "-w", "%{http_code}", "-H", "@-",
            "https://generativelanguage.googleapis.com/v1beta/models",
        ])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn();
    let Ok(mut child) = spawned else {
        return "unverified";
    };
    if let Some(mut stdin) = child.stdin.take() {
        let _ = writeln!(stdin, "x-goog-api-key: {key}");
    }
    let Ok(out) = child.wait_with_output() else {
        return "unverified";
    };
    match String::from_utf8_lossy(&out.stdout).trim().parse::<u16>() {
        Ok(200) | Ok(429) => "verified",
        Ok(400) | Ok(401) | Ok(403) => "rejected",
        _ => "unverified",
    }
}

/// Verify, then save. This used to write unconditionally and return true,
/// so "Saved ✓" meant "written to disk" - a typo'd key opened the
/// onboarding gate and failed twenty minutes later inside scoring. A
/// rejected key is NOT written: overwriting a working key with one Google
/// just refused would trade a visible failure for a silent one.
#[tauri::command]
async fn save_gemini_key(key: String) -> Result<Value, String> {
    let key = key.trim().to_string();
    if key.is_empty() {
        return Err("key is empty".to_string());
    }
    let status = gemini_key_status(&key);
    if status != "rejected" {
        let home = home_dir();
        fs::create_dir_all(&home).map_err(|e| e.to_string())?;
        let path = home.join("secrets.json");
        let mut current: Value = fs::read_to_string(&path)
            .ok()
            .and_then(|s| serde_json::from_str(&s).ok())
            .unwrap_or_else(|| json!({}));
        current["gemini_api_key"] = json!(key);
        fs::write(&path, serde_json::to_string_pretty(&current).unwrap())
            .map_err(|e| e.to_string())?;
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let _ = fs::set_permissions(&path, fs::Permissions::from_mode(0o600));
        }
    }
    Ok(json!({"status": status}))
}

#[tauri::command]
fn get_setup_state() -> Result<Value, String> {
    let secrets = home_dir().join("secrets.json");
    let has_key = fs::read_to_string(&secrets)
        .ok()
        .and_then(|s| serde_json::from_str::<Value>(&s).ok())
        .map(|v| v["gemini_api_key"].as_str().map(|k| !k.is_empty()).unwrap_or(false))
        .unwrap_or(false);
    let onboarded = home_dir().join("onboarded").exists();
    Ok(json!({"has_gemini_key": has_key, "onboarded": onboarded}))
}

#[tauri::command]
fn mark_onboarded() -> Result<(), String> {
    let home = home_dir();
    fs::create_dir_all(&home).map_err(|e| e.to_string())?;
    fs::write(home.join("onboarded"), "1").map_err(|e| e.to_string())
}

#[tauri::command]
async fn check_ollama() -> Result<Value, String> {
    let out = quiet_command("curl")
        .args(["-s", "-m", "3", "http://localhost:11434/api/tags"])
        .output()
        .map_err(|e| e.to_string())?;
    if !out.status.success() {
        return Ok(json!({"running": false, "models": []}));
    }
    let parsed: Value = serde_json::from_slice(&out.stdout).unwrap_or(json!({}));
    let models: Vec<String> = parsed["models"]
        .as_array()
        .map(|arr| arr.iter().filter_map(|m| m["name"].as_str().map(String::from)).collect())
        .unwrap_or_default();
    Ok(json!({"running": true, "models": models}))
}

/// Sync pipeline call that returns one JSON blob (edit context, visual
/// suggestions). Long-running render-clip goes through run_edit_render
/// instead so progress streams.
#[tauri::command]
async fn edit_tool(args: Vec<String>) -> Result<Value, String> {
    let (program, base_args) = pipeline_invocation();
    let mut full = base_args;
    full.push("edit".to_string());
    full.extend(args);
    let out = quiet_command(&program)
        .args(&full)
        .output()
        .map_err(|e| e.to_string())?;
    let stdout = String::from_utf8_lossy(&out.stdout);
    // last JSON line is the payload (progress lines may precede it)
    let line = stdout.lines().rev().find(|l| l.trim_start().starts_with('{'));
    match line.and_then(|l| serde_json::from_str::<Value>(l).ok()) {
        Some(v) => Ok(v),
        None => Err(format!(
            "edit tool produced no JSON: {}",
            String::from_utf8_lossy(&out.stderr).chars().take(400).collect::<String>()
        )),
    }
}

/// Settings panel bridge: `publikclip settings <verb> [...]` → one JSON blob.
/// Same shape as edit_tool (the pipeline owns the schema and validation; the
/// panel just renders whatever it is handed).
#[tauri::command]
async fn settings_tool(args: Vec<String>) -> Result<Value, String> {
    let (program, base_args) = pipeline_invocation();
    let mut full = base_args;
    full.push("settings".to_string());
    full.extend(args);
    let out = quiet_command(&program)
        .args(&full)
        .output()
        .map_err(|e| e.to_string())?;
    let stdout = String::from_utf8_lossy(&out.stdout);
    // Library import warnings can precede the payload, so take the last JSON line.
    let line = stdout.lines().rev().find(|l| l.trim_start().starts_with('{'));
    match line.and_then(|l| serde_json::from_str::<Value>(l).ok()) {
        Some(v) => Ok(v),
        None => Err(format!(
            "settings tool produced no JSON: {}",
            String::from_utf8_lossy(&out.stderr).chars().take(400).collect::<String>()
        )),
    }
}

#[tauri::command]
fn run_edit_render(app: AppHandle, job_id: String, clip: u32) -> Result<(), String> {
    spawn_tool(
        &app,
        vec![
            "--jsonl".to_string(),
            "edit".to_string(),
            "render-clip".to_string(),
            job_id,
            clip.to_string(),
        ],
    );
    Ok(())
}

#[tauri::command]
fn save_clip_edits(job_id: String, edits: Value) -> Result<(), String> {
    let path = home_dir().join("jobs").join(&job_id).join("clip_edits.json");
    // Merge: the app sends one clip's state at a time; other clips' edits
    // must survive.
    let mut current: Value = fs::read_to_string(&path)
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or_else(|| json!({}));
    if let (Some(obj), Some(new)) = (current.as_object_mut(), edits.as_object()) {
        for (k, v) in new {
            obj.insert(k.clone(), v.clone());
        }
    }
    fs::write(&path, serde_json::to_string_pretty(&current).unwrap()).map_err(|e| e.to_string())
}

#[tauri::command]
fn save_pexels_key(key: String) -> Result<bool, String> {
    let home = home_dir();
    fs::create_dir_all(&home).map_err(|e| e.to_string())?;
    let path = home.join("secrets.json");
    let mut current: Value = fs::read_to_string(&path)
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or_else(|| json!({}));
    current["pexels_api_key"] = json!(key.trim());
    fs::write(&path, serde_json::to_string_pretty(&current).unwrap()).map_err(|e| e.to_string())?;
    Ok(true)
}

#[tauri::command]
fn ig_status() -> Result<Value, String> {
    let path = home_dir().join("instagram.json");
    let connected = fs::read_to_string(&path)
        .ok()
        .and_then(|s| serde_json::from_str::<Value>(&s).ok());
    match connected {
        Some(v) => Ok(json!({
            "connected": true,
            "username": v["username"],
            "obtained_at": v["token_obtained_at"],
        })),
        None => Ok(json!({"connected": false})),
    }
}

/// Runs the CLI's OAuth dance (it opens the browser + catches the localhost
/// callback). Blocking by design — the frontend shows a "finish in your
/// browser" state until this returns.
#[tauri::command]
async fn ig_connect(app_id: String, app_secret: String) -> Result<String, String> {
    let (program, base_args) = pipeline_invocation();
    let mut args = base_args;
    args.extend([
        "ig".into(), "connect".into(),
        "--app-id".into(), app_id,
        "--app-secret".into(), app_secret,
    ]);
    let out = quiet_command(&program)
        .args(&args)
        .output()
        .map_err(|e| e.to_string())?;
    let stdout = String::from_utf8_lossy(&out.stdout).trim().to_string();
    let stderr = String::from_utf8_lossy(&out.stderr).trim().to_string();
    if out.status.success() {
        Ok(stdout)
    } else {
        Err(if stderr.is_empty() { stdout } else { stderr })
    }
}

/// One-shot `publikclip ig <args...>` call returning the CLI's JSON line
/// (sync / overview / link / unlink / reject — same contract as edit_tool).
#[tauri::command]
async fn ig_tool(args: Vec<String>) -> Result<Value, String> {
    let (program, base_args) = pipeline_invocation();
    let mut full = base_args;
    full.push("ig".to_string());
    full.extend(args);
    let out = quiet_command(&program)
        .args(&full)
        .output()
        .map_err(|e| e.to_string())?;
    let stdout = String::from_utf8_lossy(&out.stdout);
    let line = stdout.lines().rev().find(|l| l.trim_start().starts_with('{'));
    match line.and_then(|l| serde_json::from_str::<Value>(l).ok()) {
        Some(v) => Ok(v),
        None => Err(format!(
            "ig tool produced no JSON: {}",
            String::from_utf8_lossy(&out.stderr).chars().take(400).collect::<String>()
        )),
    }
}

#[tauri::command]
fn export_clip(path: String, title: Option<String>) -> Result<String, String> {
    let src = PathBuf::from(&path);
    if !src.exists() {
        return Err("clip file missing".into());
    }
    let downloads = dirs_home().join("Downloads");
    let stem = title.unwrap_or_else(|| "Alias Studio".into());
    let safe: String = stem
        .chars()
        .map(|c| if c.is_alphanumeric() || c == ' ' || c == '-' { c } else { '_' })
        .collect::<String>()
        .trim()
        .replace(' ', "-")
        .chars()
        .take(60)
        .collect();
    let mut dest = downloads.join(format!("{safe}.mp4"));
    let mut n = 1;
    while dest.exists() {
        dest = downloads.join(format!("{safe}-{n}.mp4"));
        n += 1;
    }
    fs::copy(&src, &dest).map_err(|e| e.to_string())?;
    Ok(dest.to_string_lossy().to_string())
}

fn main() {
    tauri::Builder::default()
        .manage(RunState(Mutex::new(QueueState {
            active: None,
            cancel_latch: false,
            paused: false,
        })))
        .manage(QueueCache(Mutex::new(QueueCacheInner { gen: 0, jobs: None })))
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            resume_job,
            cancel_job,
            enqueue_job,
            start_queue,
            set_queue_paused,
            queue_state,
            cancel_pending_job,
            job_results,
            list_job_dirs,
            save_gemini_key,
            get_setup_state,
            mark_onboarded,
            check_ollama,
            ig_status,
            ig_connect,
            ig_tool,
            edit_tool,
            settings_tool,
            run_edit_render,
            save_clip_edits,
            save_pexels_key,
            export_clip
        ])
        .setup(|app| {
            let _ = app.get_webview_window("main");
            // App-start reconciliation: ghost 'running' rows become truthful
            // before the queue can be looked at. The queue itself never
            // auto-starts at launch - a user reopening the app to look at a
            // finished clip must not find the GPU busy.
            let handle = app.handle().clone();
            std::thread::spawn(move || {
                let _ = one_shot_json(&["jobs".to_string(), "reconcile".to_string()]);
                // Warm the queue cache only after reconcile made the rows
                // truthful - the view opens against this.
                refresh_queue_cache(&handle);
            });
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Alias Studio");
}
