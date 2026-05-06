#![allow(dead_code)]

pub const NVS_NAMESPACE_SERVER: &str = "server_cfg";
pub const NVS_KEY_HOST: &str = "host";
pub const NVS_KEY_PORT: &str = "port";
pub const DEFAULT_HOST: &str = "192.168.51.17";
pub const DEFAULT_PORT: u16 = 8080;
pub const TIMEOUT_MS: u32 = 5_000;
pub const RESPONSE_BUF_SIZE: usize = 256;
pub const AUDIO_RESP_CHUNK_SIZE: usize = 2048;
pub const AUDIO_RESP_MAX_SIZE: usize = 350_000;
pub const NET_SILENCE_THRESHOLD: i16 = 500;
pub const NET_SILENCE_PAD_SAMPLES: usize = 1_280;
pub const NET_MAX_PCM_BYTES: usize = 70_400;
