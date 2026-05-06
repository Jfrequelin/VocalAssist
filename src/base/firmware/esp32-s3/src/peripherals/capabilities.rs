use heapless::String;

#[derive(Debug, Clone)]
pub struct DeviceCapabilities {
    pub audio_input: bool,
    pub audio_output: bool,
    pub display_present: bool,
    pub display_shape: &'static str,
    pub display_width: u16,
    pub display_height: u16,
    pub touch: bool,
    pub camera: bool,
    pub max_uplink_chunk_bytes: usize,
    pub max_downlink_chunk_bytes: usize,
}

impl DeviceCapabilities {
    pub fn describe(&self) -> String<256> {
        let mut s = String::new();
        let _ = core::fmt::write(
            &mut s,
            format_args!(
                "audio_in={} audio_out={} display={} {}x{} shape={} touch={} camera={} up={} down={}",
                self.audio_input,
                self.audio_output,
                self.display_present,
                self.display_width,
                self.display_height,
                self.display_shape,
                self.touch,
                self.camera,
                self.max_uplink_chunk_bytes,
                self.max_downlink_chunk_bytes,
            ),
        );
        s
    }
}

pub fn default_device_capabilities() -> DeviceCapabilities {
    DeviceCapabilities {
        audio_input: true,
        audio_output: true,
        display_present: true,
        display_shape: "round",
        display_width: 360,
        display_height: 360,
        touch: true,
        camera: false,
        max_uplink_chunk_bytes: 16_384,
        max_downlink_chunk_bytes: 16_384,
    }
}
