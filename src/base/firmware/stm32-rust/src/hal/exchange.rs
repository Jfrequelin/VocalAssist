//! Format d'echange unifie firmware ↔ assistant.
//!
//! Objectif : eviter les formats ad hoc par peripherique et exposer un contrat
//! stable par type de donnees.
//!
//! Types pris en charge :
//! - audio PCM/flux compresse
//! - image PNG/JPEG/RGB565
//! - texte UTF-8
//! - variables typées (bool, entier, decimal fixe, texte)
//! - binaire generique
//!
//! Le cas audio reste compatible avec le contrat Python existant
//! `EdgeAudioRequest` via [`AssistantPacket::to_edge_audio_request_json`].

use core::fmt::Write;

use super::{encode_base64, HalError, IoBuffer, TextBuffer};

/// Buffer JSON pour serialisation embarquee sans allocation dynamique.
pub type JsonBuffer = heapless::String<4096>;

/// Type canonique de donnees echangees.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DataKind {
    Audio,
    Image,
    Text,
    Variable,
    Binary,
}

impl DataKind {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Audio => "audio",
            Self::Image => "image",
            Self::Text => "text",
            Self::Variable => "variable",
            Self::Binary => "binary",
        }
    }
}

/// Encodage associe au contenu du paquet.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DataEncoding {
    Pcm16Le,
    Opus,
    Png,
    Jpeg,
    Rgb565,
    Utf8,
    Json,
    Raw,
}

impl DataEncoding {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Pcm16Le => "pcm16le",
            Self::Opus => "opus",
            Self::Png => "png",
            Self::Jpeg => "jpeg",
            Self::Rgb565 => "rgb565",
            Self::Utf8 => "utf8",
            Self::Json => "json",
            Self::Raw => "raw",
        }
    }
}

/// Valeur typée pour les variables firmware/assistant.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum VariableValue {
    Bool(bool),
    Int(i32),
    UInt(u32),
    /// Nombre decimal fixe en milli-unites pour eviter les floats en `no_std`.
    FixedMilli(i32),
    Text(TextBuffer),
}

/// Metadonnees audio.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AudioPayload {
    pub sample_rate_hz: u32,
    pub channels: u8,
    pub encoding: DataEncoding,
    pub bytes: IoBuffer,
}

/// Metadonnees image.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ImagePayload {
    pub width: u16,
    pub height: u16,
    pub encoding: DataEncoding,
    pub bytes: IoBuffer,
}

/// Payload texte.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TextPayload {
    pub encoding: DataEncoding,
    pub text: TextBuffer,
}

/// Payload variable.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct VariablePayload {
    pub name: heapless::String<64>,
    pub value: VariableValue,
}

/// Payload binaire generique.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BinaryPayload {
    pub mime_type: heapless::String<64>,
    pub bytes: IoBuffer,
}

/// Charge utile typée d'un paquet firmware ↔ assistant.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum AssistantPayload {
    Audio(AudioPayload),
    Image(ImagePayload),
    Text(TextPayload),
    Variable(VariablePayload),
    Binary(BinaryPayload),
}

impl AssistantPayload {
    pub fn kind(&self) -> DataKind {
        match self {
            Self::Audio(_) => DataKind::Audio,
            Self::Image(_) => DataKind::Image,
            Self::Text(_) => DataKind::Text,
            Self::Variable(_) => DataKind::Variable,
            Self::Binary(_) => DataKind::Binary,
        }
    }
}

/// Enveloppe canonique echangee entre firmware et assistant.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AssistantPacket {
    pub correlation_id: heapless::String<64>,
    pub device_id: heapless::String<64>,
    pub timestamp_ms: u64,
    pub payload: AssistantPayload,
}

impl AssistantPacket {
    pub fn new(
        correlation_id: &str,
        device_id: &str,
        timestamp_ms: u64,
        payload: AssistantPayload,
    ) -> Result<Self, HalError> {
        let mut correlation_id_buf = heapless::String::new();
        correlation_id_buf
            .push_str(correlation_id)
            .map_err(|_| HalError::BufferOverflow)?;
        let mut device_id_buf = heapless::String::new();
        device_id_buf
            .push_str(device_id)
            .map_err(|_| HalError::BufferOverflow)?;
        if correlation_id_buf.is_empty() || device_id_buf.is_empty() {
            return Err(HalError::InvalidArgument);
        }

        Ok(Self {
            correlation_id: correlation_id_buf,
            device_id: device_id_buf,
            timestamp_ms,
            payload,
        })
    }

    pub fn audio_pcm16(
        correlation_id: &str,
        device_id: &str,
        timestamp_ms: u64,
        sample_rate_hz: u32,
        channels: u8,
        audio_bytes: &[u8],
    ) -> Result<Self, HalError> {
        let mut bytes = IoBuffer::new();
        bytes.extend_from_slice(audio_bytes)
            .map_err(|_| HalError::BufferOverflow)?;
        Self::new(
            correlation_id,
            device_id,
            timestamp_ms,
            AssistantPayload::Audio(AudioPayload {
                sample_rate_hz,
                channels,
                encoding: DataEncoding::Pcm16Le,
                bytes,
            }),
        )
    }

    pub fn text_utf8(
        correlation_id: &str,
        device_id: &str,
        timestamp_ms: u64,
        text: &str,
    ) -> Result<Self, HalError> {
        let mut text_buf = TextBuffer::new();
        text_buf.push_str(text).map_err(|_| HalError::BufferOverflow)?;
        Self::new(
            correlation_id,
            device_id,
            timestamp_ms,
            AssistantPayload::Text(TextPayload {
                encoding: DataEncoding::Utf8,
                text: text_buf,
            }),
        )
    }

    pub fn variable_bool(
        correlation_id: &str,
        device_id: &str,
        timestamp_ms: u64,
        name: &str,
        value: bool,
    ) -> Result<Self, HalError> {
        let mut name_buf = heapless::String::new();
        name_buf.push_str(name).map_err(|_| HalError::BufferOverflow)?;
        Self::new(
            correlation_id,
            device_id,
            timestamp_ms,
            AssistantPayload::Variable(VariablePayload {
                name: name_buf,
                value: VariableValue::Bool(value),
            }),
        )
    }

    pub fn kind(&self) -> DataKind {
        self.payload.kind()
    }

    /// Serialise le paquet dans un format JSON canonique.
    pub fn to_wire_json(&self) -> Result<JsonBuffer, HalError> {
        let mut json = JsonBuffer::new();
        write!(
            json,
            "{{\"correlation_id\":\"{}\",\"device_id\":\"{}\",\"timestamp_ms\":{},\"kind\":\"{}\",\"payload\":",
            self.correlation_id,
            self.device_id,
            self.timestamp_ms,
            self.kind().as_str(),
        )
        .map_err(|_| HalError::BufferOverflow)?;
        self.write_payload_json(&mut json)?;
        json.push('}').map_err(|_| HalError::BufferOverflow)?;
        Ok(json)
    }

    /// Serialise le cas audio selon le contrat Python `EdgeAudioRequest`.
    pub fn to_edge_audio_request_json(&self) -> Result<JsonBuffer, HalError> {
        let AssistantPayload::Audio(audio) = &self.payload else {
            return Err(HalError::InvalidArgument);
        };

        let mut audio_base64 = TextBuffer::new();
        encode_base64(&audio.bytes, &mut audio_base64)?;

        let mut json = JsonBuffer::new();
        write!(
            json,
            "{{\"correlation_id\":\"{}\",\"device_id\":\"{}\",\"timestamp_ms\":{},\"sample_rate_hz\":{},\"channels\":{},\"encoding\":\"{}\",\"audio_base64\":\"{}\"}}",
            self.correlation_id,
            self.device_id,
            self.timestamp_ms,
            audio.sample_rate_hz,
            audio.channels,
            audio.encoding.as_str(),
            audio_base64,
        )
        .map_err(|_| HalError::BufferOverflow)?;
        Ok(json)
    }

    fn write_payload_json(&self, json: &mut JsonBuffer) -> Result<(), HalError> {
        match &self.payload {
            AssistantPayload::Audio(audio) => {
                let mut base64 = TextBuffer::new();
                encode_base64(&audio.bytes, &mut base64)?;
                write!(
                    json,
                    "{{\"encoding\":\"{}\",\"sample_rate_hz\":{},\"channels\":{},\"data_base64\":\"{}\"}}",
                    audio.encoding.as_str(),
                    audio.sample_rate_hz,
                    audio.channels,
                    base64,
                )
                .map_err(|_| HalError::BufferOverflow)?;
            }
            AssistantPayload::Image(image) => {
                let mut base64 = TextBuffer::new();
                encode_base64(&image.bytes, &mut base64)?;
                write!(
                    json,
                    "{{\"encoding\":\"{}\",\"width\":{},\"height\":{},\"data_base64\":\"{}\"}}",
                    image.encoding.as_str(),
                    image.width,
                    image.height,
                    base64,
                )
                .map_err(|_| HalError::BufferOverflow)?;
            }
            AssistantPayload::Text(text) => {
                write!(
                    json,
                    "{{\"encoding\":\"{}\",\"text\":\"",
                    text.encoding.as_str(),
                )
                .map_err(|_| HalError::BufferOverflow)?;
                push_json_escaped(json, text.text.as_str())?;
                json.push_str("\"}").map_err(|_| HalError::BufferOverflow)?;
            }
            AssistantPayload::Variable(variable) => {
                write!(json, "{{\"name\":\"{}\",\"value_type\":\"", variable.name)
                    .map_err(|_| HalError::BufferOverflow)?;
                match &variable.value {
                    VariableValue::Bool(value) => {
                        json.push_str("bool\",\"value\":")
                            .map_err(|_| HalError::BufferOverflow)?;
                        json.push_str(if *value { "true" } else { "false" })
                            .map_err(|_| HalError::BufferOverflow)?;
                    }
                    VariableValue::Int(value) => {
                        write!(json, "int\",\"value\":{}", value)
                            .map_err(|_| HalError::BufferOverflow)?;
                    }
                    VariableValue::UInt(value) => {
                        write!(json, "uint\",\"value\":{}", value)
                            .map_err(|_| HalError::BufferOverflow)?;
                    }
                    VariableValue::FixedMilli(value) => {
                        write!(json, "fixed_milli\",\"value\":{}", value)
                            .map_err(|_| HalError::BufferOverflow)?;
                    }
                    VariableValue::Text(value) => {
                        json.push_str("text\",\"value\":\"")
                            .map_err(|_| HalError::BufferOverflow)?;
                        push_json_escaped(json, value.as_str())?;
                        json.push('"').map_err(|_| HalError::BufferOverflow)?;
                    }
                }
                json.push('}').map_err(|_| HalError::BufferOverflow)?;
            }
            AssistantPayload::Binary(binary) => {
                let mut base64 = TextBuffer::new();
                encode_base64(&binary.bytes, &mut base64)?;
                write!(
                    json,
                    "{{\"mime_type\":\"{}\",\"data_base64\":\"{}\"}}",
                    binary.mime_type,
                    base64,
                )
                .map_err(|_| HalError::BufferOverflow)?;
            }
        }
        Ok(())
    }
}

fn push_json_escaped(dst: &mut JsonBuffer, src: &str) -> Result<(), HalError> {
    for ch in src.chars() {
        match ch {
            '"' => dst.push_str("\\\"").map_err(|_| HalError::BufferOverflow)?,
            '\\' => dst.push_str("\\\\").map_err(|_| HalError::BufferOverflow)?,
            '\n' => dst.push_str("\\n").map_err(|_| HalError::BufferOverflow)?,
            '\r' => dst.push_str("\\r").map_err(|_| HalError::BufferOverflow)?,
            '\t' => dst.push_str("\\t").map_err(|_| HalError::BufferOverflow)?,
            _ => dst.push(ch).map_err(|_| HalError::BufferOverflow)?,
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn audio_packet_keeps_existing_python_contract() {
        let packet = AssistantPacket::audio_pcm16(
            "corr-1",
            "edge-001",
            1234,
            16_000,
            1,
            b"ABCD",
        )
        .unwrap();

        let json = packet.to_edge_audio_request_json().unwrap();
        assert!(json.contains("\"correlation_id\":\"corr-1\""));
        assert!(json.contains("\"device_id\":\"edge-001\""));
        assert!(json.contains("\"sample_rate_hz\":16000"));
        assert!(json.contains("\"channels\":1"));
        assert!(json.contains("\"encoding\":\"pcm16le\""));
        assert!(json.contains("\"audio_base64\":\"QUJDRA==\""));
    }

    #[test]
    fn text_packet_serialises_to_canonical_wire_format() {
        let packet = AssistantPacket::text_utf8("corr-2", "edge-001", 5678, "bonjour").unwrap();
        let json = packet.to_wire_json().unwrap();
        assert!(json.contains("\"kind\":\"text\""));
        assert!(json.contains("\"encoding\":\"utf8\""));
        assert!(json.contains("\"text\":\"bonjour\""));
    }

    #[test]
    fn variable_packet_serialises_bool() {
        let packet = AssistantPacket::variable_bool("corr-3", "edge-001", 42, "muted", true)
            .unwrap();
        let json = packet.to_wire_json().unwrap();
        assert!(json.contains("\"kind\":\"variable\""));
        assert!(json.contains("\"name\":\"muted\""));
        assert!(json.contains("\"value_type\":\"bool\""));
        assert!(json.contains("\"value\":true"));
    }

    #[test]
    fn image_packet_serialises_dimensions_and_encoding() {
        let mut bytes = IoBuffer::new();
        bytes.extend_from_slice(&[1, 2, 3, 4]).unwrap();
        let packet = AssistantPacket::new(
            "corr-4",
            "edge-001",
            99,
            AssistantPayload::Image(ImagePayload {
                width: 360,
                height: 360,
                encoding: DataEncoding::Png,
                bytes,
            }),
        )
        .unwrap();
        let json = packet.to_wire_json().unwrap();
        assert!(json.contains("\"kind\":\"image\""));
        assert!(json.contains("\"width\":360"));
        assert!(json.contains("\"height\":360"));
        assert!(json.contains("\"encoding\":\"png\""));
    }
}