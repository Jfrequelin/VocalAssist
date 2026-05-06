
use anyhow::Result;

mod app;
mod audio;
mod buffers;
mod config;
mod ha_client;
mod server;
mod lcd;
mod netlog;
mod peripherals;
mod touch;
mod ui;
mod wake_word;
mod wifi;

fn main() -> Result<()> {
    esp_idf_svc::sys::link_patches();
    esp_idf_svc::log::EspLogger::initialize_default();
    app::run()
}
