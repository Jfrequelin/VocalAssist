use std::net::UdpSocket;
use std::sync::{Mutex, OnceLock};

pub const DEFAULT_LOG_PORT: u16 = 15140;
const MAX_LOG_BYTES: usize = 900;

struct RemoteSink {
    socket: UdpSocket,
    target: String,
}

static REMOTE_SINK: OnceLock<Mutex<Option<RemoteSink>>> = OnceLock::new();

fn sink_cell() -> &'static Mutex<Option<RemoteSink>> {
    REMOTE_SINK.get_or_init(|| Mutex::new(None))
}

pub fn init(host: &str, port: u16) -> anyhow::Result<()> {
    let target = format!("{}:{}", host, port);
    let socket = UdpSocket::bind("0.0.0.0:0")?;
    socket.connect(&target)?;
    socket.set_nonblocking(true)?;

    let mut guard = sink_cell().lock().expect("netlog mutex poisoned");
    *guard = Some(RemoteSink { socket, target });
    Ok(())
}

pub fn target() -> Option<String> {
    let guard = sink_cell().lock().ok()?;
    guard.as_ref().map(|s| s.target.clone())
}

pub fn send(level: &str, message: &str) {
    let payload = if message.len() > MAX_LOG_BYTES {
        &message[..MAX_LOG_BYTES]
    } else {
        message
    };
    let line = format!("[{}] {}", level, payload);

    let guard = match sink_cell().lock() {
        Ok(g) => g,
        Err(_) => return,
    };
    if let Some(sink) = guard.as_ref() {
        let _ = sink.socket.send(line.as_bytes());
    }
}

pub fn info(message: &str) {
    send("INFO", message);
}

pub fn warn(message: &str) {
    send("WARN", message);
}

pub fn error(message: &str) {
    send("ERROR", message);
}
