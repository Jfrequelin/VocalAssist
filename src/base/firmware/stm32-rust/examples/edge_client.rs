use std::env;
use std::io::{Read, Write};
use std::net::TcpStream;
use std::time::{SystemTime, UNIX_EPOCH};

use base64::engine::general_purpose::STANDARD;
use base64::Engine;
use edge_base::{Config, Runtime, process_transcript};

fn extract_json_string_field(body: &str, field: &str) -> Option<String> {
    let needle = format!("\"{}\": \"", field);
    let start = body.find(&needle)? + needle.len();
    let tail = &body[start..];
    let end = tail.find('"')?;
    Some(tail[..end].to_string())
}

fn parse_base_url(base_url: &str) -> (&str, u16) {
    let trimmed = base_url.trim();
    let no_scheme = trimmed.strip_prefix("http://").unwrap_or(trimmed);
    let host_port = no_scheme.split('/').next().unwrap_or(no_scheme);
    match host_port.split_once(':') {
        Some((host, port)) => (host, port.parse().unwrap_or(8081)),
        None => (host_port, 8081),
    }
}

fn current_timestamp_ms() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("system time before unix epoch")
        .as_millis()
}

fn main() {
    let base_url = env::var("EDGE_BACKEND_URL")
        .unwrap_or_else(|_| "http://host.docker.internal:8081".to_string());
    let device_id = env::var("EDGE_DEVICE_ID").unwrap_or_else(|_| "stm32-rust-docker".to_string());
    let transcript = env::var("EDGE_TRANSCRIPT")
        .unwrap_or_else(|_| "nova allume la lumiere du salon".to_string());

    let config = Config::new("nova");
    let mut runtime = Runtime::new(&config);
    let decision = process_transcript(&mut runtime, &config, &transcript);

    if !decision.should_send {
        eprintln!("firmware rejected transcript: {:?}", decision.result);
        std::process::exit(2);
    }

    let command = decision.command.unwrap_or("");
    let audio_base64 = STANDARD.encode(command.as_bytes());
    let correlation_id = format!("cid-{}", current_timestamp_ms());
    let body = format!(
        concat!(
            "{{",
            "\"correlation_id\":\"{}\",",
            "\"device_id\":\"{}\",",
            "\"timestamp_ms\":{},",
            "\"sample_rate_hz\":16000,",
            "\"channels\":1,",
            "\"encoding\":\"pcm16le\",",
            "\"audio_base64\":\"{}\"",
            "}}"
        ),
        correlation_id,
        device_id,
        current_timestamp_ms(),
        audio_base64
    );

    let (host, port) = parse_base_url(&base_url);
    let mut stream = TcpStream::connect((host, port)).expect("connect backend");
    let request = format!(
        concat!(
            "POST /edge/audio HTTP/1.1\r\n",
            "Host: {}:{}\r\n",
            "Content-Type: application/json\r\n",
            "Content-Length: {}\r\n",
            "Connection: close\r\n\r\n",
            "{}"
        ),
        host,
        port,
        body.len(),
        body
    );

    stream
        .write_all(request.as_bytes())
        .expect("send request");

    let mut response = String::new();
    stream.read_to_string(&mut response).expect("read response");

    let response_body = response
        .split("\r\n\r\n")
        .nth(1)
        .unwrap_or_default();
    let answer = extract_json_string_field(response_body, "answer")
        .unwrap_or_else(|| "reponse backend absente".to_string());

    println!("Firmware transcript: {}", transcript);
    println!("Firmware command: {}", command);
    println!("Firmware TTS: {}", answer);
    println!("Backend response:\n{}", response);
}
