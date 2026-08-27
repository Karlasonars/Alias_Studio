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
    job_id: Option<String>, // learned from the sidecar's 'job' JSONL event
    child_pid: u32,
    cancel_requested: bool,
    #[cfg(target_os = "windows")]
    job: Option<job_object::JobHandle>, // None: adoption failed -> taskkill fallback
}

struct RunState(Mutex<Option<ActiveRun>>);

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
    let run = guard.as_mut().ok_or_else(|| "no job is running".to_string())?;
    run.cancel_requested = true;
    if let Some(id) = &run.job_id {
        let dir = home_dir().join("jobs").join(id);
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
    if let Some(id) = &run.job_id {
        let (program, base_args) = pipeline_invocation();
        let mut args = base_args;
        args.push("jobs".to_string());
        args.push("mark-cancelled".to_string());
        args.push(id.clone());
        let mut status_after: Option<String> = None;
        if let Ok(out) = quiet_command(&program).args(&args).output() {
            let stdout = String::from_utf8_lossy(&out.stdout);
            if let Some(line) = stdout.lines().rev().find(|l| l.trim_start().starts_with('{')) {
                if let Ok(v) = serde_json::from_str::<Value>(line) {
                    status_after = v["status"].as_str().map(String::from);
                }
            }
        }
        // The cancel raced the job's own completion: nothing was cancelled,
        // so take back the marker cancel_job optimistically wrote.
        if clean_exit && status_after.as_deref() == Some("done") {
            let _ = fs::remove_file(home_dir().join("jobs").join(id).join(CANCELLED_MARKER));
        }
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
fn run_job(
    app: AppHandle,
    source: String,
    llm: Option<String>,
    captions: Option<String>,
    gameplay_amount: Option<f64>,
) -> Result<(), String> {
    let (program, base_args) = pipeline_invocation();
    std::thread::spawn(move || {
        let mut args = base_args.clone();
        args.push("--jsonl".to_string());
        args.push("run".to_string());
        args.push(source);
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
        stream_pipeline(&app, &program, &args, PipelineKind::Job);
    });
    Ok(())
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
    let (program, base_args) = pipeline_invocation();
    std::thread::spawn(move || {
        let mut args = base_args.clone();
        args.push("--jsonl".to_string());
        args.push("resume".to_string());
        args.push(job_id);
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
        stream_pipeline(&app, &program, &args, PipelineKind::Job);
    });
    Ok(())
}

fn stream_pipeline(app: &AppHandle, program: &str, args: &[String], kind: PipelineKind) {
    let mut cmd = quiet_command(program);
    cmd.args(args).stdout(Stdio::piped()).stderr(Stdio::piped());
    // Job runs get their own process group on unix so cancel_job can killpg
    // the whole tree. UNVERIFIED on real macOS until T-19 lands.
    #[cfg(unix)]
    if kind == PipelineKind::Job {
        use std::os::unix::process::CommandExt;
        cmd.process_group(0);
    }
    let child = cmd.spawn();
    let mut child = match child {
        Ok(c) => c,
        Err(err) => {
            let _ = app.emit(
                "pipeline-event",
                json!({"event": "result", "ok": false, "error": format!("could not start pipeline: {err}")}),
            );
            return;
        }
    };
    if kind == PipelineKind::Job {
        #[cfg(target_os = "windows")]
        let job = job_object::JobHandle::adopt(&child);
        *app.state::<RunState>().0.lock().unwrap() = Some(ActiveRun {
            job_id: None,
            child_pid: child.id(),
            cancel_requested: false,
            #[cfg(target_os = "windows")]
            job,
        });
    }
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
                // run_job can't know its job id at spawn; the sidecar's own
                // 'job' event is where it is learned.
                if kind == PipelineKind::Job && value["event"] == "job" {
                    if let Some(id) = value["job_id"].as_str() {
                        if let Some(run) = app.state::<RunState>().0.lock().unwrap().as_mut() {
                            run.job_id = Some(id.to_string());
                        }
                    }
                }
                let _ = app.emit("pipeline-event", value);
            }
        }
    }
    let status = child.wait();
    if let Some(t) = stderr_thread {
        let _ = t.join();
    }
    if kind == PipelineKind::Job {
        let finished = app.state::<RunState>().0.lock().unwrap().take();
        if let Some(run) = finished {
            if run.cancel_requested {
                handle_cancelled_exit(app, &run, status.as_ref().ok());
                return; // deliberate stop - never the 'exited' crash path
            }
        }
    }
    if let Ok(status) = status {
        if !status.success() {
            let detail = stderr_tail.lock().unwrap().trim().to_string();
            let _ = app.emit(
                "pipeline-event",
                json!({"event": "exited", "code": status.code(), "stderr": detail}),
            );
        }
    }
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

#[tauri::command]
fn save_gemini_key(key: String) -> Result<bool, String> {
    let home = home_dir();
    fs::create_dir_all(&home).map_err(|e| e.to_string())?;
    let path = home.join("secrets.json");
    let mut current: Value = fs::read_to_string(&path)
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or_else(|| json!({}));
    current["gemini_api_key"] = json!(key.trim());
    fs::write(&path, serde_json::to_string_pretty(&current).unwrap()).map_err(|e| e.to_string())?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = fs::set_permissions(&path, fs::Permissions::from_mode(0o600));
    }
    Ok(true)
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
    let (program, base_args) = pipeline_invocation();
    std::thread::spawn(move || {
        let mut args = base_args.clone();
        args.push("--jsonl".to_string());
        args.push("edit".to_string());
        args.push("render-clip".to_string());
        args.push(job_id);
        args.push(clip.to_string());
        stream_pipeline(&app, &program, &args, PipelineKind::Tool);
    });
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
        .manage(RunState(Mutex::new(None)))
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            run_job,
            resume_job,
            cancel_job,
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
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Alias Studio");
}
