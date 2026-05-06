#![allow(dead_code)]

//! buffers.rs — Buffers thread-safe pour audio et vidéo

use anyhow::Result;
use log::info;
use std::sync::{Arc, Mutex, mpsc};

// ── Ring buffer audio (capture microphone) ──────────────────────────────────

/// Ring buffer circulaire pour l'audio capturé.
/// Permet au producteur (I2S RX) et consommateur (traitement) de travailler à des vitesses différentes.
pub struct AudioRingBuffer {
    buffer: Vec<u8>,
    write_pos: usize,
    read_pos: usize,
    size: usize,
    mutex: Mutex<()>,
}

impl AudioRingBuffer {
    /// Crée un ring buffer de `capacity` bytes.
    pub fn new(capacity: usize) -> Self {
        info!("[BUFFERS] AudioRingBuffer créé: {} bytes", capacity);
        Self {
            buffer: vec![0u8; capacity],
            write_pos: 0,
            read_pos: 0,
            size: capacity,
            mutex: Mutex::new(()),
        }
    }

    /// Écrit des données dans le ring buffer (mode FIFO).
    /// Si le buffer est plein, écrase les anciennes données.
    pub fn write(&mut self, data: &[u8]) -> Result<usize> {
        let _lock = self.mutex.lock().unwrap();
        
        let mut written = 0;
        for &byte in data {
            self.buffer[self.write_pos] = byte;
            self.write_pos = (self.write_pos + 1) % self.size;
            written += 1;
        }
        
        // Si on a rattrapé le lecteur, avancer le lecteur
        if self.write_pos == self.read_pos && written > 0 {
            self.read_pos = (self.read_pos + 1) % self.size;
        }
        
        Ok(written)
    }

    /// Lit jusqu'à `max_len` bytes du ring buffer.
    pub fn read(&mut self, max_len: usize) -> Result<Vec<u8>> {
        let _lock = self.mutex.lock().unwrap();
        
        let mut result = Vec::with_capacity(max_len);
        let mut count = 0;
        
        while count < max_len && self.read_pos != self.write_pos {
            result.push(self.buffer[self.read_pos]);
            self.read_pos = (self.read_pos + 1) % self.size;
            count += 1;
        }
        
        Ok(result)
    }

    /// Retourne le nombre de bytes disponibles pour lecture.
    pub fn available(&self) -> usize {
        let _lock = self.mutex.lock().unwrap();
        
        if self.write_pos >= self.read_pos {
            self.write_pos - self.read_pos
        } else {
            self.size - self.read_pos + self.write_pos
        }
    }

    /// Vide complètement le buffer.
    pub fn clear(&mut self) {
        let _lock = self.mutex.lock().unwrap();
        self.read_pos = self.write_pos;
    }
}

// ── Channel audio Rust (pour découpler production/consommation) ────────────

/// Wrapper autour d'un mpsc channel Rust pour passer des chunks audio entre tasks.
/// Utilise les channels Rust plutôt que FreeRTOS pour plus de portabilité.
pub struct AudioChannel {
    sender: mpsc::Sender<Vec<u8>>,
    receiver: mpsc::Receiver<Vec<u8>>,
}

impl AudioChannel {
    /// Crée un nouveau channel audio (FIFO non borné).
    pub fn new() -> Self {
        let (tx, rx) = mpsc::channel();
        info!("[BUFFERS] AudioChannel créé");
        Self {
            sender: tx,
            receiver: rx,
        }
    }

    /// Retourne le sender pour un thread producteur.
    pub fn sender(&self) -> mpsc::Sender<Vec<u8>> {
        self.sender.clone()
    }

    /// Retourne le receiver pour un thread consommateur.
    pub fn receiver(&self) -> &mpsc::Receiver<Vec<u8>> {
        &self.receiver
    }

    /// Envoie un buffer. Bloquant si pas de récepteur.
    pub fn send(&self, data: Vec<u8>) -> Result<()> {
        self.sender
            .send(data)
            .map_err(|e| anyhow::anyhow!("[BUFFERS] AudioChannel::send failed: {}", e))
    }

    /// Reçoit un buffer (bloquant).
    pub fn receive(&self) -> Result<Vec<u8>> {
        self.receiver
            .recv()
            .map_err(|e| anyhow::anyhow!("[BUFFERS] AudioChannel::receive failed: {}", e))
    }

    /// Reçoit avec timeout (essai de recv_timeout si dispo).
    pub fn receive_timeout(&self, timeout: std::time::Duration) -> Result<Vec<u8>> {
        self.receiver
            .recv_timeout(timeout)
            .map_err(|e| anyhow::anyhow!("[BUFFERS] AudioChannel::receive_timeout failed: {}", e))
    }
}

// ── Double buffer vidéo (LCD) ──────────────────────────────────────────────

/// Double buffer pour la vidéo LCD.
/// Permet la mise à jour sans tearing : un buffer est affiché, l'autre est modifié.
pub struct LcdDoubleBuffer<T: Clone> {
    /// Buffer actuellement affiché à l'écran
    front: Arc<Mutex<T>>,
    /// Buffer en cours de modification
    back: Arc<Mutex<T>>,
}

impl<T: Clone> LcdDoubleBuffer<T> {
    /// Crée un double buffer avec une valeur initiale `init`.
    pub fn new(init: T) -> Self {
        info!("[BUFFERS] LcdDoubleBuffer créé");
        Self {
            front: Arc::new(Mutex::new(init.clone())),
            back: Arc::new(Mutex::new(init)),
        }
    }

    /// Obtient une référence au buffer en modification (back).
    pub fn get_back(&self) -> Arc<Mutex<T>> {
        self.back.clone()
    }

    /// Obtient une référence au buffer affiché (front).
    pub fn get_front(&self) -> Arc<Mutex<T>> {
        self.front.clone()
    }

    /// Échange front et back (après avoir modifié back).
    pub fn swap(&mut self) {
        let tmp = self.front.clone();
        self.front = self.back.clone();
        self.back = tmp;
    }
}

// ── Statistiques buffers ────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct BufferStats {
    pub audio_ring_available: usize,
}

impl BufferStats {
    pub fn log(&self) {
        info!("[BUFFERS] Ring: {} bytes available", self.audio_ring_available);
    }
}
