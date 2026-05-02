//! HAL (Hardware Abstraction Layer) — ESP32-S3 / Waveshare ESP32-S3-Touch-LCD-1.85C
//!
//! Un module par périphérique physique présent sur la carte cible.
//!
//! # Structure
//!
//! | Module          | Périphérique cible                        | Bus      |
//! |-----------------|-------------------------------------------|----------|
//! | [`microphone`]  | ES7210 (V2) / MEMS (V1)                   | I2S      |
//! | [`playback`]    | ES8311 (V2) / PCM5101APWR (V1)            | I2S      |
//! | [`display`]     | LCD rond 360×360 (ST7701S)                | SPI+GPIO |
//! | [`exchange`]    | Format d'echange firmware ↔ assistant     | Logique  |
//! | [`touch`]       | Capteur capacitif I2C + INT               | I2C      |
//! | [`led`]         | LED d'état GPIO                           | GPIO     |
//! | [`rtc`]         | PCF85063ATL                               | I2C      |
//! | [`battery`]     | Surveillance Li-ion (BAT_ADC)             | ADC      |
//! | [`storage`]     | Carte TF/SD (FAT32)                       | SDIO/SPI |
//! | [`button`]      | Bouton physique GPIO                      | GPIO     |
//!
//! # Entrées / Sorties — modèle générique
//!
//! Le firmware échange des données avec son environnement selon deux formes :
//!
//! | Forme     | Type Rust              | Usage typique                             |
//! |-----------|------------------------|-------------------------------------------|
//! | Binaire   | [`IoBuffer`]           | PCM audio, trames réseau, logs binaires   |
//! | Texte     | [`heapless::String`]   | Transcription STT, réponse TTS, commandes |
//!
//! Les traits génériques [`HalReader`] et [`HalWriter`] définissent le contrat
//! d'E/S buffer.  [`HalTextReader`] et [`HalTextWriter`] en sont la variante texte.
//!
//! ```
//! # use edge_base::hal::{HalWriter, HalReader, IoBuffer, HalError};
//! # struct Sink; impl HalWriter for Sink {
//! #   fn write_buf(&mut self, data: &[u8]) -> Result<usize, HalError> { Ok(data.len()) }
//! #   fn flush(&mut self) -> Result<(), HalError> { Ok(()) }
//! # }
//! # struct Source { pos: usize }
//! # impl HalReader for Source {
//! #   fn read_buf(&mut self, buf: &mut IoBuffer) -> Result<usize, HalError> { Ok(0) }
//! #   fn bytes_available(&self) -> usize { 0 }
//! # }
//! let mut sink = Sink {};
//! let written = sink.write_buf(b"hello").unwrap();
//! assert_eq!(written, 5);
//! ```
//!
//! # Compatibilité
//!
//! Toutes les abstractions sont `no_std` et s'appuient sur les traits
//! [`embedded-hal 1.x`](https://docs.rs/embedded-hal/1.0) pour rester
//! portables entre STM32 et ESP32-S3.
//!
//! Les implémentations concrètes pour ESP32-S3 sont activées via le feature
//! `esp32s3` de ce crate.

#![allow(dead_code)]

pub mod battery;
pub mod button;
pub mod display;
pub mod exchange;
pub mod led;
pub mod microphone;
pub mod playback;
pub mod rtc;
pub mod storage;
pub mod touch;

// ─── Erreurs communes ────────────────────────────────────────────────────────

/// Erreur générique d'un périphérique HAL.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum HalError {
    /// Le périphérique n'a pas encore été initialisé (open non appelé).
    NotInitialised,
    /// Le périphérique est occupé (opération en cours).
    Busy,
    /// Erreur de communication sur le bus (I2C NACK, SPI timeout…).
    BusError,
    /// Argument invalide passé à la méthode HAL.
    InvalidArgument,
    /// Dépassement de capacité interne (buffer, queue…).
    BufferOverflow,
    /// Périphérique absent ou non détecté.
    DeviceNotFound,
    /// Erreur générique non classée.
    Other,
}

// ─── Trait de base ───────────────────────────────────────────────────────────

/// Trait commun à tout périphérique HAL.
///
/// Cycle de vie attendu :
/// ```ignore
/// device.open()?;
/// // utilisation
/// device.close();
/// ```
pub trait HalDevice {
    /// Initialise et active le périphérique.
    fn open(&mut self) -> Result<(), HalError>;
    /// Libère les ressources et désactive le périphérique.
    fn close(&mut self);
    /// Indique si le périphérique est opérationnel.
    fn is_ready(&self) -> bool;
}

// ─── Buffer d'E/S ────────────────────────────────────────────────────────────

/// Buffer d'E/S partagé entre tous les modules HAL.
///
/// Taille maximale : 4 096 octets (suffisant pour une trame PCM 16 kHz / 128 ms
/// en mono 16 bits, ou un payload JSON `EdgeAudioRequest` encodé en base64).
///
/// Utilisé aussi bien pour les données binaires (PCM, réseau) que pour les
/// chaînes UTF-8 (transcription STT, réponse TTS).
pub type IoBuffer = heapless::Vec<u8, 4096>;

/// Buffer texte partagé entre tous les modules HAL.
///
/// Taille maximale : 512 caractères UTF-8.
pub type TextBuffer = heapless::String<512>;

// ─── Traits d'entrée / sortie binaires ───────────────────────────────────────

/// Trait de **lecture** binaire depuis un périphérique ou un canal.
///
/// Implémenté par :
/// - la couche de réception réseau (WiFi → backend),
/// - le microphone (lecture trame PCM I2S),
/// - le stockage TF/SD (lecture fichier).
///
/// # Contrat
/// `read_buf` remplit `buf` au maximum de sa capacité et retourne le nombre
/// d'octets effectivement lus.  Retourne `Ok(0)` si aucune donnée n'est
/// disponible (non-bloquant).
pub trait HalReader {
    /// Lit des octets disponibles dans `buf`.
    ///
    /// # Errors
    /// - [`HalError::NotInitialised`] — périphérique non ouvert.
    /// - [`HalError::BusError`] — erreur de communication.
    /// - [`HalError::BufferOverflow`] — `buf` trop petit pour la trame entrante.
    fn read_buf(&mut self, buf: &mut IoBuffer) -> Result<usize, HalError>;

    /// Retourne le nombre d'octets immédiatement disponibles sans bloquer.
    fn bytes_available(&self) -> usize;
}

/// Trait d'**écriture** binaire vers un périphérique ou un canal.
///
/// Implémenté par :
/// - la couche d'envoi réseau (edge → backend),
/// - le DAC audio (écriture trame PCM I2S),
/// - le stockage TF/SD (écriture fichier/log).
///
/// # Contrat
/// `write_buf` envoie tout ou partie de `data` et retourne le nombre d'octets
/// effectivement transmis.  `flush` garantit que tous les octets en attente
/// ont été envoyés au périphérique physique.
pub trait HalWriter {
    /// Envoie `data` vers le périphérique ou le canal.
    ///
    /// # Errors
    /// - [`HalError::NotInitialised`] — périphérique non ouvert.
    /// - [`HalError::Busy`] — ressource occupée, réessayer.
    /// - [`HalError::BufferOverflow`] — file interne pleine.
    fn write_buf(&mut self, data: &[u8]) -> Result<usize, HalError>;

    /// Vide les buffers internes et force l'envoi effectif.
    ///
    /// # Errors
    /// [`HalError::BusError`] si le flush échoue au niveau matériel.
    fn flush(&mut self) -> Result<(), HalError>;
}

// ─── Traits d'entrée / sortie texte ──────────────────────────────────────────

/// Trait de **lecture texte** depuis un périphérique ou un canal.
///
/// Implémenté par :
/// - la couche de réception STT (réponse serveur → transcription),
/// - le port UART de debug,
/// - le stockage TF/SD (lecture ligne de configuration).
///
/// # Contrat
/// `read_line` remplit `buf` avec la prochaine ligne disponible (sans `\n`).
/// Retourne `Ok(0)` si aucune ligne complète n'est encore disponible.
pub trait HalTextReader {
    /// Lit la prochaine ligne UTF-8 disponible dans `buf`.
    ///
    /// # Errors
    /// - [`HalError::NotInitialised`] — canal non ouvert.
    /// - [`HalError::BufferOverflow`] — ligne trop longue pour `buf`.
    /// - [`HalError::BusError`] — données malformées (UTF-8 invalide).
    fn read_line(&mut self, buf: &mut TextBuffer) -> Result<usize, HalError>;

    /// Retourne `true` si une ligne complète est disponible.
    fn line_available(&self) -> bool;
}

/// Trait d'**écriture texte** vers un périphérique ou un canal.
///
/// Implémenté par :
/// - le port UART de debug,
/// - l'affichage LCD (délégation à `DisplayHal::show_text`),
/// - le stockage TF/SD (écriture log ligne par ligne).
///
/// # Contrat
/// `write_str` transmet la chaîne `s` telle quelle (sans `\n` automatique).
/// `write_line` ajoute `\n` en fin de chaîne.
pub trait HalTextWriter {
    /// Transmet la chaîne `s`.
    ///
    /// # Errors
    /// - [`HalError::NotInitialised`] — canal non ouvert.
    /// - [`HalError::BufferOverflow`] — file interne pleine.
    fn write_str(&mut self, s: &str) -> Result<(), HalError>;

    /// Transmet `s` suivi d'un saut de ligne (`\n`).
    ///
    /// # Errors
    /// Mêmes variantes que [`write_str`](HalTextWriter::write_str).
    fn write_line(&mut self, s: &str) -> Result<(), HalError> {
        self.write_str(s)?;
        self.write_str("\n")
    }
}

// ─── Codec : binaire ↔ texte ─────────────────────────────────────────────────

/// Encode `src` en Base64 vers `dst` (format utilisé dans `EdgeAudioRequest.audio_base64`).
///
/// Retourne le nombre de caractères écrits.
///
/// # Errors
/// [`HalError::BufferOverflow`] si `dst` est trop petit.
pub fn encode_base64(src: &[u8], dst: &mut TextBuffer) -> Result<usize, HalError> {
    const TABLE: &[u8; 64] =
        b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut written = 0usize;
    let mut i = 0usize;
    while i < src.len() {
        let b0 = src[i] as u32;
        let b1 = if i + 1 < src.len() { src[i + 1] as u32 } else { 0 };
        let b2 = if i + 2 < src.len() { src[i + 2] as u32 } else { 0 };
        let chunk = (b0 << 16) | (b1 << 8) | b2;
        let chars = [
            TABLE[((chunk >> 18) & 0x3F) as usize] as char,
            TABLE[((chunk >> 12) & 0x3F) as usize] as char,
            if i + 1 < src.len() { TABLE[((chunk >> 6) & 0x3F) as usize] as char } else { '=' },
            if i + 2 < src.len() { TABLE[(chunk & 0x3F) as usize] as char } else { '=' },
        ];
        for c in chars {
            dst.push(c).map_err(|_| HalError::BufferOverflow)?;
            written += 1;
        }
        i += 3;
    }
    Ok(written)
}

/// Décode une chaîne Base64 `src` vers `dst`.
///
/// Retourne le nombre d'octets écrits.
///
/// # Errors
/// - [`HalError::InvalidArgument`] si `src` contient des caractères invalides.
/// - [`HalError::BufferOverflow`] si `dst` est trop petit.
pub fn decode_base64(src: &str, dst: &mut IoBuffer) -> Result<usize, HalError> {
    fn val(c: u8) -> Result<u32, HalError> {
        match c {
            b'A'..=b'Z' => Ok((c - b'A') as u32),
            b'a'..=b'z' => Ok((c - b'a' + 26) as u32),
            b'0'..=b'9' => Ok((c - b'0' + 52) as u32),
            b'+' => Ok(62),
            b'/' => Ok(63),
            b'=' => Ok(0),
            _ => Err(HalError::InvalidArgument),
        }
    }
    let bytes = src.as_bytes();
    let mut written = 0usize;
    let mut i = 0usize;
    while i + 3 < bytes.len() {
        let v0 = val(bytes[i])?;
        let v1 = val(bytes[i + 1])?;
        let v2 = val(bytes[i + 2])?;
        let v3 = val(bytes[i + 3])?;
        let chunk = (v0 << 18) | (v1 << 12) | (v2 << 6) | v3;
        dst.push(((chunk >> 16) & 0xFF) as u8)
            .map_err(|_| HalError::BufferOverflow)?;
        written += 1;
        if bytes[i + 2] != b'=' {
            dst.push(((chunk >> 8) & 0xFF) as u8)
                .map_err(|_| HalError::BufferOverflow)?;
            written += 1;
        }
        if bytes[i + 3] != b'=' {
            dst.push((chunk & 0xFF) as u8)
                .map_err(|_| HalError::BufferOverflow)?;
            written += 1;
        }
        i += 4;
    }
    Ok(written)
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── Implémentations de test ───────────────────────────────────────────────

    struct MemWriter {
        buf: IoBuffer,
        flushed: bool,
    }
    impl MemWriter {
        fn new() -> Self {
            Self { buf: IoBuffer::new(), flushed: false }
        }
    }
    impl HalWriter for MemWriter {
        fn write_buf(&mut self, data: &[u8]) -> Result<usize, HalError> {
            let mut written = 0;
            for &b in data {
                self.buf.push(b).map_err(|_| HalError::BufferOverflow)?;
                written += 1;
            }
            Ok(written)
        }
        fn flush(&mut self) -> Result<(), HalError> {
            self.flushed = true;
            Ok(())
        }
    }

    struct MemReader {
        src: IoBuffer,
        pos: usize,
    }
    impl MemReader {
        fn from_bytes(data: &[u8]) -> Self {
            let mut src = IoBuffer::new();
            src.extend_from_slice(data).unwrap();
            Self { src, pos: 0 }
        }
    }
    impl HalReader for MemReader {
        fn read_buf(&mut self, buf: &mut IoBuffer) -> Result<usize, HalError> {
            let mut count = 0;
            while self.pos < self.src.len() {
                buf.push(self.src[self.pos]).map_err(|_| HalError::BufferOverflow)?;
                self.pos += 1;
                count += 1;
            }
            Ok(count)
        }
        fn bytes_available(&self) -> usize {
            self.src.len() - self.pos
        }
    }

    struct TextSink {
        out: TextBuffer,
    }
    impl TextSink {
        fn new() -> Self { Self { out: TextBuffer::new() } }
    }
    impl HalTextWriter for TextSink {
        fn write_str(&mut self, s: &str) -> Result<(), HalError> {
            self.out.push_str(s).map_err(|_| HalError::BufferOverflow)
        }
    }

    // ── Tests HalWriter ───────────────────────────────────────────────────────

    #[test]
    fn writer_stores_bytes() {
        let mut w = MemWriter::new();
        let n = w.write_buf(b"hello").unwrap();
        assert_eq!(n, 5);
        assert_eq!(&w.buf[..], b"hello");
    }

    #[test]
    fn writer_flush_sets_flag() {
        let mut w = MemWriter::new();
        w.flush().unwrap();
        assert!(w.flushed);
    }

    // ── Tests HalReader ───────────────────────────────────────────────────────

    #[test]
    fn reader_delivers_all_bytes() {
        let mut r = MemReader::from_bytes(b"world");
        assert_eq!(r.bytes_available(), 5);
        let mut buf = IoBuffer::new();
        let n = r.read_buf(&mut buf).unwrap();
        assert_eq!(n, 5);
        assert_eq!(&buf[..], b"world");
        assert_eq!(r.bytes_available(), 0);
    }

    // ── Tests HalTextWriter / write_line ─────────────────────────────────────

    #[test]
    fn text_writer_write_line_appends_newline() {
        let mut sink = TextSink::new();
        sink.write_line("nova bonjour").unwrap();
        assert_eq!(sink.out.as_str(), "nova bonjour\n");
    }

    // ── Tests encode_base64 ───────────────────────────────────────────────────

    #[test]
    fn base64_encode_empty() {
        let mut out = TextBuffer::new();
        let n = encode_base64(b"", &mut out).unwrap();
        assert_eq!(n, 0);
        assert!(out.is_empty());
    }

    #[test]
    fn base64_encode_man() {
        // "Man" → "TWFu"
        let mut out = TextBuffer::new();
        encode_base64(b"Man", &mut out).unwrap();
        assert_eq!(out.as_str(), "TWFu");
    }

    #[test]
    fn base64_encode_one_byte_padding() {
        // "M" → "TQ=="
        let mut out = TextBuffer::new();
        encode_base64(b"M", &mut out).unwrap();
        assert_eq!(out.as_str(), "TQ==");
    }

    #[test]
    fn base64_encode_two_bytes_padding() {
        // "Ma" → "TWE="
        let mut out = TextBuffer::new();
        encode_base64(b"Ma", &mut out).unwrap();
        assert_eq!(out.as_str(), "TWE=");
    }

    // ── Tests decode_base64 ───────────────────────────────────────────────────

    #[test]
    fn base64_decode_man() {
        let mut dst = IoBuffer::new();
        let n = decode_base64("TWFu", &mut dst).unwrap();
        assert_eq!(n, 3);
        assert_eq!(&dst[..], b"Man");
    }

    #[test]
    fn base64_decode_one_byte_padding() {
        let mut dst = IoBuffer::new();
        decode_base64("TQ==", &mut dst).unwrap();
        assert_eq!(&dst[..], b"M");
    }

    #[test]
    fn base64_roundtrip() {
        let original = b"nova allume la lumiere";
        let mut encoded = TextBuffer::new();
        encode_base64(original, &mut encoded).unwrap();
        let mut decoded = IoBuffer::new();
        decode_base64(encoded.as_str(), &mut decoded).unwrap();
        assert_eq!(&decoded[..], original);
    }

    #[test]
    fn base64_invalid_char_returns_error() {
        let mut dst = IoBuffer::new();
        assert_eq!(decode_base64("TW!u", &mut dst), Err(HalError::InvalidArgument));
    }
}
