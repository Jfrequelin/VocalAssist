/// ui.rs — Écrans applicatifs (provisioning WiFi, statut, clavier tactile)

use crate::lcd::{LcdDisplay, TouchPoint, COLOR_BLACK, COLOR_BLUE, COLOR_GRAY, COLOR_GREEN,
                 COLOR_ORANGE, COLOR_RED, COLOR_WHITE, LCD_W, LCD_H};
use anyhow::Result;
use esp_idf_hal::delay::FreeRtos;
use esp_idf_sys::esp_timer_get_time;
use heapless;
use log::info;

use embedded_graphics::{
    mono_font::{ascii::{FONT_9X15, FONT_10X20}, MonoTextStyle},
    pixelcolor::Rgb565,
    prelude::*,
    text::Text,
};

// Couleurs embedded-graphics (correspondance avec les u16 existants)
const EG_WHITE:  Rgb565 = Rgb565::new(31, 63, 31);
const EG_BLACK:  Rgb565 = Rgb565::new(0, 0, 0);
const EG_BLUE:   Rgb565 = Rgb565::new(0, 0, 31);
const EG_GREEN:  Rgb565 = Rgb565::new(0, 63, 0);
const EG_RED:    Rgb565 = Rgb565::new(31, 0, 0);
const EG_ORANGE: Rgb565 = Rgb565::new(31, 41, 0);

/// Affiche une ligne de texte (police 9×15).
fn draw_text(lcd: &mut LcdDisplay, text: &str, x: i32, y: i32) -> Result<()> {
    let style = MonoTextStyle::new(&FONT_9X15, EG_WHITE);
    Text::new(text, Point::new(x, y), style).draw(lcd)?;
    Ok(())
}

/// Affiche une ligne de texte (police 9×15) avec couleur personnalisée.
fn draw_text_color(lcd: &mut LcdDisplay, text: &str, x: i32, y: i32, color: Rgb565) -> Result<()> {
    let style = MonoTextStyle::new(&FONT_9X15, color);
    Text::new(text, Point::new(x, y), style).draw(lcd)?;
    Ok(())
}

/// Affiche une ligne de texte en grand (10×20).
fn draw_text_lg(lcd: &mut LcdDisplay, text: &str, x: i32, y: i32, color: Rgb565) -> Result<()> {
    let style = MonoTextStyle::new(&FONT_10X20, color);
    Text::new(text, Point::new(x, y), style).draw(lcd)?;
    Ok(())
}

// ----------------------------------------------------------------
// Clavier tactile compact
// Disposition : 5 rangées, 7 colonnes visibles
// Modes : lettres / chiffres / symboles (bascule dédiée)
// Rangée 4 : MODE + BKSP + OK
// ----------------------------------------------------------------

const KB_ROWS: usize = 5;
const KB_COLS: usize = 7;
const KB_KEY_W: u16 = 48;
const KB_KEY_H: u16 = 34;
const KB_KEY_GAP: u16 = 2;
const KB_ORIGIN_X: u16 = 6;
const KB_ORIGIN_Y: u16 = 132;

const BACK_BTN_LEFT_X: u16 = 40;   // bouton retour à gauche (liste SSID)
const BACK_BTN_RIGHT_X: u16 = 220; // bouton retour à droite (saisie mot de passe)
const BACK_BTN_W: u16 = 88;
const BACK_BTN_H: u16 = 24;
const BACK_BTN_TOP_Y: u16 = 56;  // y dans la liste SSID
const BACK_BTN_PASS_Y: u16 = 50; // y dans l'écran mot de passe (même ligne que SSID)

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum KeyboardMode {
    Letters,
    Numbers,
    Symbols,
}

static KB_LAYOUT_LETTERS: [&[u8; KB_COLS]; 4] = [
    b"abcdefg",
    b"hijklmn",
    b"opqrstu",
    b"vwxyz-_",
];

static KB_LAYOUT_NUMBERS: [&[u8; KB_COLS]; 4] = [
    b"1234567",
    b"890@._-",
    b"!?/:;()",
    b"+*#%=,&",
];

static KB_LAYOUT_SYMBOLS: [&[u8; KB_COLS]; 4] = [
    b"!@#$%^&",
    b"*()_+-=",
    b"[]{}?/|",
    b".,:;`~\\",
];

fn kb_char(mode: KeyboardMode, row: usize, col: usize) -> char {
    match mode {
        KeyboardMode::Letters => KB_LAYOUT_LETTERS[row][col] as char,
        KeyboardMode::Numbers => KB_LAYOUT_NUMBERS[row][col] as char,
        KeyboardMode::Symbols => KB_LAYOUT_SYMBOLS[row][col] as char,
    }
}

fn next_mode(mode: KeyboardMode) -> KeyboardMode {
    match mode {
        KeyboardMode::Letters => KeyboardMode::Numbers,
        KeyboardMode::Numbers => KeyboardMode::Symbols,
        KeyboardMode::Symbols => KeyboardMode::Letters,
    }
}

fn mode_button_label(mode: KeyboardMode) -> &'static str {
    match mode {
        KeyboardMode::Letters => "123",
        KeyboardMode::Numbers => "#+=",
        KeyboardMode::Symbols => "ABC",
    }
}

fn draw_back_button(lcd: &mut LcdDisplay, x: u16, y: u16) -> Result<()> {
    lcd.fill_rect(x, y, BACK_BTN_W, BACK_BTN_H, COLOR_BLUE)?;
    draw_text_color(lcd, "< RETOUR", x as i32 + 8, y as i32 + 17, EG_WHITE)?;
    Ok(())
}

fn is_back_touch(p: TouchPoint, x: u16, y: u16) -> bool {
    p.x >= x && p.x < x + BACK_BTN_W && p.y >= y && p.y < y + BACK_BTN_H
}

fn draw_char_key(
    lcd: &mut LcdDisplay,
    mode: KeyboardMode,
    row: usize,
    col: usize,
    bg: u16,
    fg: Rgb565,
) -> Result<()> {
    let kx = KB_ORIGIN_X + col as u16 * (KB_KEY_W + KB_KEY_GAP);
    let ky = KB_ORIGIN_Y + row as u16 * (KB_KEY_H + KB_KEY_GAP);
    lcd.fill_rect(kx + 1, ky + 1, KB_KEY_W - 2, KB_KEY_H - 2, bg)?;

    let ch = kb_char(mode, row, col);
    let mut key_label = heapless::String::<1>::new();
    let _ = key_label.push(ch);
    let tx = kx as i32 + 19;
    let ty = ky as i32 + 24;
    draw_text_color(lcd, key_label.as_str(), tx, ty, fg)?;
    Ok(())
}

fn draw_special_key_mode(lcd: &mut LcdDisplay, mode: KeyboardMode, bg: u16, fg: Rgb565) -> Result<()> {
    let third = LCD_W / 3;
    let ky = KB_ORIGIN_Y + 4 * (KB_KEY_H + KB_KEY_GAP);
    lcd.fill_rect(1, ky + 1, third - 2, KB_KEY_H - 2, bg)?;
    draw_text_color(lcd, mode_button_label(mode), 40, ky as i32 + 22, fg)?;
    Ok(())
}

fn draw_special_key_backspace(lcd: &mut LcdDisplay, bg: u16, fg: Rgb565) -> Result<()> {
    let third = LCD_W / 3;
    let ky = KB_ORIGIN_Y + 4 * (KB_KEY_H + KB_KEY_GAP);
    lcd.fill_rect(third + 1, ky + 1, third - 2, KB_KEY_H - 2, bg)?;
    draw_text_color(lcd, "EFF", third as i32 + 42, ky as i32 + 22, fg)?;
    Ok(())
}

fn draw_special_key_ok(lcd: &mut LcdDisplay, bg: u16, fg: Rgb565) -> Result<()> {
    let third = LCD_W / 3;
    let ky = KB_ORIGIN_Y + 4 * (KB_KEY_H + KB_KEY_GAP);
    lcd.fill_rect(third * 2 + 1, ky + 1, LCD_W - third * 2 - 2, KB_KEY_H - 2, bg)?;
    draw_text_color(lcd, "OK", (third * 2) as i32 + 50, ky as i32 + 22, fg)?;
    Ok(())
}

fn keyboard_flash_pressed(lcd: &mut LcdDisplay, p: TouchPoint, mode: KeyboardMode) -> Result<KeyPress> {
    let key = keyboard_hit_test(p, mode);
    match key {
        KeyPress::Char(_) => {
            let row = ((p.y - KB_ORIGIN_Y) / (KB_KEY_H + KB_KEY_GAP)) as usize;
            let col = ((p.x - KB_ORIGIN_X) / (KB_KEY_W + KB_KEY_GAP)) as usize;
            if row < KB_ROWS - 1 && col < KB_COLS {
                draw_char_key(lcd, mode, row, col, COLOR_GREEN, EG_BLACK)?;
                FreeRtos::delay_ms(50);
                draw_char_key(lcd, mode, row, col, COLOR_WHITE, EG_BLACK)?;
            }
        }
        KeyPress::ModeSwitch => {
            draw_special_key_mode(lcd, mode, COLOR_WHITE, EG_BLACK)?;
            FreeRtos::delay_ms(50);
            draw_special_key_mode(lcd, mode, COLOR_BLUE, EG_WHITE)?;
        }
        KeyPress::Backspace => {
            draw_special_key_backspace(lcd, COLOR_WHITE, EG_BLACK)?;
            FreeRtos::delay_ms(50);
            draw_special_key_backspace(lcd, COLOR_ORANGE, EG_BLACK)?;
        }
        KeyPress::Confirm => {
            draw_special_key_ok(lcd, COLOR_WHITE, EG_BLACK)?;
            FreeRtos::delay_ms(50);
            draw_special_key_ok(lcd, COLOR_GREEN, EG_BLACK)?;
        }
        KeyPress::None => {}
    }
    Ok(key)
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum KeyPress {
    Char(char),
    ModeSwitch,
    Backspace,
    Confirm,
    None,
}

pub fn keyboard_hit_test(p: TouchPoint, mode: KeyboardMode) -> KeyPress {
    if p.y < KB_ORIGIN_Y {
        return KeyPress::None;
    }
    let row = ((p.y - KB_ORIGIN_Y) / (KB_KEY_H + KB_KEY_GAP)) as usize;
    if row >= KB_ROWS {
        return KeyPress::None;
    }
    // Rangée spéciale (4) : MODE + BKSP + OK
    if row == 4 {
        let third = LCD_W / 3;
        if p.x < third {
            return KeyPress::ModeSwitch;
        }
        if p.x < third * 2 {
            return KeyPress::Backspace;
        }
        return KeyPress::Confirm;
    }
    if p.x < KB_ORIGIN_X {
        return KeyPress::None;
    }
    let col = ((p.x - KB_ORIGIN_X) / (KB_KEY_W + KB_KEY_GAP)) as usize;
    if col >= KB_COLS {
        return KeyPress::None;
    }
    KeyPress::Char(kb_char(mode, row, col))
}

pub fn keyboard_draw(lcd: &mut LcdDisplay, mode: KeyboardMode) -> Result<()> {
    lcd.fill_rect(0, KB_ORIGIN_Y, LCD_W, LCD_H - KB_ORIGIN_Y, COLOR_GRAY)?;
    for row in 0..KB_ROWS - 1 {
        for col in 0..KB_COLS {
            draw_char_key(lcd, mode, row, col, COLOR_WHITE, EG_BLACK)?;
        }
    }
    draw_special_key_mode(lcd, mode, COLOR_BLUE, EG_WHITE)?;
    draw_special_key_backspace(lcd, COLOR_ORANGE, EG_BLACK)?;
    draw_special_key_ok(lcd, COLOR_GREEN, EG_BLACK)?;
    Ok(())
}

/// Redessine uniquement le contenu du champ de saisie (intérieur du cadre).
/// Rapide : pas de redessinage du titre, SSID, contour ni du clavier.
fn draw_password_field(lcd: &mut LcdDisplay, password: &str, reveal_last_char: bool) -> Result<()> {
    // Efface uniquement l'intérieur du cadre
    lcd.fill_rect(23, 81, 314, 38, COLOR_BLACK)?;

    let mut masked = heapless::String::<64>::new();
    let total = password.chars().count();
    for (idx, c) in password.chars().enumerate() {
        if reveal_last_char && idx + 1 == total {
            let _ = masked.push(c);
        } else {
            let _ = masked.push('*');
        }
    }

    let mut pwd_line = heapless::String::<72>::new();
    let _ = pwd_line.push_str("PWD: ");
    for c in masked.chars().take(60) {
        let _ = pwd_line.push(c);
    }
    draw_text_color(lcd, pwd_line.as_str(), 30, 106, EG_GREEN)?;
    Ok(())
}

/// Redessine l'écran complet de saisie (bannière, titre, SSID, cadre, contenu).
/// Appeler uniquement à l'initialisation ou après Backspace.
fn draw_password_screen(lcd: &mut LcdDisplay, ssid: &str, password: &str, reveal_last_char: bool) -> Result<()> {
    lcd.fill_rect(0, 0, LCD_W, KB_ORIGIN_Y, COLOR_BLACK)?;
    lcd.draw_banner(0, 32, COLOR_BLUE)?;
    // Titre centré dans la bannière (17 chars × 10px = 170px → x=(360-170)/2=95)
    draw_text_lg(lcd, "Mot de passe WiFi", 95, 24, EG_WHITE)?;

    // Bouton retour à droite, sur la même ligne que le SSID
    draw_back_button(lcd, BACK_BTN_RIGHT_X, BACK_BTN_PASS_Y)?;

    // SSID limité à 14 chars avec "..." si tronqué
    let mut ssid_display = heapless::String::<20>::new();
    let ssid_chars: usize = ssid.chars().count();
    if ssid_chars > 14 {
        for c in ssid.chars().take(14) { let _ = ssid_display.push(c); }
        let _ = ssid_display.push_str("...");
    } else {
        for c in ssid.chars() { let _ = ssid_display.push(c); }
    }
    let mut ssid_line = heapless::String::<28>::new();
    let _ = ssid_line.push_str("SSID: ");
    for c in ssid_display.chars() { let _ = ssid_line.push(c); }
    draw_text(lcd, ssid_line.as_str(), 20, 62)?;

    // Cadre de saisie (fond blanc + intérieur noir)
    lcd.fill_rect(20, 78, 320, 44, COLOR_WHITE)?;
    lcd.fill_rect(22, 80, 316, 40, COLOR_BLACK)?;

    draw_password_field(lcd, password, reveal_last_char)?;
    Ok(())
}

fn now_us() -> i64 {
    unsafe { esp_timer_get_time() }
}

// ----------------------------------------------------------------
// Écran : statut WiFi
// ----------------------------------------------------------------

pub fn show_wifi_connecting(lcd: &mut LcdDisplay) -> Result<()> {
    lcd.fill(COLOR_BLACK)?;
    // Titre centré dans la zone circulaire visible (x≥50, y≥65)
    lcd.fill_rect(50, 130, 260, 40, COLOR_BLUE)?;
    draw_text_lg(lcd, "Connexion WiFi...", 60, 156, EG_WHITE)?;
    draw_text(lcd, "Authentification en cours", 68, 185)?;
    info!("UI: Connexion WiFi en cours...");
    Ok(())
}

pub fn show_wifi_connected(lcd: &mut LcdDisplay, ip: &str) -> Result<()> {
    lcd.fill(COLOR_BLACK)?;
    lcd.fill_rect(50, 130, 260, 40, COLOR_GREEN)?;
    draw_text_lg(lcd, "WiFi connecte !", 72, 156, EG_BLACK)?;
    let mut line = heapless::String::<32>::new();
    let _ = line.push_str("IP: ");
    for c in ip.chars().take(24) { let _ = line.push(c); }
    draw_text(lcd, line.as_str(), 80, 185)?;
    info!("UI: WiFi connecté — IP {}", ip);
    Ok(())
}

pub fn show_wifi_failed(lcd: &mut LcdDisplay) -> Result<()> {
    lcd.fill(COLOR_BLACK)?;
    lcd.fill_rect(50, 120, 260, 40, COLOR_RED)?;
    draw_text_lg(lcd, "Echec WiFi", 100, 146, EG_WHITE)?;
    draw_text(lcd, "Verif. SSID / mot de passe", 60, 175)?;
    draw_text(lcd, "Redemarrage dans 5s...", 70, 192)?;
    info!("UI: WiFi — échec connexion");
    Ok(())
}

// ----------------------------------------------------------------
// Écran : résultat ping serveur
// ----------------------------------------------------------------

pub fn show_server_ok(lcd: &mut LcdDisplay, version: &str, latency_ms: u32) -> Result<()> {
    lcd.fill(COLOR_BLACK)?;
    lcd.fill_rect(50, 140, 260, 40, COLOR_GREEN)?;
    draw_text_lg(lcd, "Serveur OK", 100, 166, EG_BLACK)?;
    let mut line = heapless::String::<32>::new();
    let _ = line.push_str("v");
    for c in version.chars().take(10) { let _ = line.push(c); }
    let _ = line.push_str("  ");
    let ms_str = format_u32(latency_ms);
    for c in ms_str.iter().copied().map(|b| b as char) { let _ = line.push(c); }
    let _ = line.push_str("ms");
    draw_text(lcd, line.as_str(), 90, 195)?;
    info!("UI: Serveur OK ✓ — v{} {}ms", version, latency_ms);
    Ok(())
}

pub fn show_server_unreachable(lcd: &mut LcdDisplay) -> Result<()> {
    lcd.fill(COLOR_BLACK)?;
    lcd.fill_rect(50, 140, 260, 40, COLOR_RED)?;
    draw_text_lg(lcd, "Serveur KO", 100, 166, EG_WHITE)?;
    draw_text(lcd, "Injoignable", 110, 195)?;
    info!("UI: Serveur injoignable ✗");
    Ok(())
}

/// Formate un u32 en tableau de chiffres ASCII (sans allocation heap).
fn format_u32(mut n: u32) -> heapless::Vec<u8, 10> {
    let mut buf = heapless::Vec::<u8, 10>::new();
    if n == 0 { let _ = buf.push(b'0'); return buf; }
    let mut tmp = [0u8; 10];
    let mut i = 0;
    while n > 0 { tmp[i] = b'0' + (n % 10) as u8; n /= 10; i += 1; }
    for j in (0..i).rev() { let _ = buf.push(tmp[j]); }
    buf
}

// ----------------------------------------------------------------
// Écran : provisioning WiFi complet
// Retourne (ssid, password) saisis par l'utilisateur
// ----------------------------------------------------------------

pub fn run_wifi_provisioning(
    lcd: &mut LcdDisplay,
    ssids: &[&str],
) -> Result<(heapless::String<32>, heapless::String<64>)> {
    use heapless::String as HString;

    'provision: loop {

    // --- Affichage liste SSIDs avec scroll ---
    // Zone circulaire : x=50..310 (w=260) est sûre pour y=65..295
    lcd.fill(COLOR_BLACK)?;
    draw_back_button(lcd, BACK_BTN_LEFT_X, BACK_BTN_TOP_Y)?;
    // Titre centré (y≈65 : chord ≈ 285 px)
    draw_text_lg(lcd, "Reseaux WiFi", 96, 75, EG_WHITE)?;
    info!("UI: {} réseaux disponibles", ssids.len());

    // Séparateur sous le titre
    lcd.fill_rect(50, 82, 260, 2, COLOR_BLUE)?;

    const SSID_ITEM_H: u16 = 30;
    const SSID_ITEM_GAP: u16 = 4;
    const SSID_ORIGIN_Y: u16 = 90;  // y≥90 → zone d'affichage sûre
    const SSID_MAX_Y: u16 = 290;     // y≤290 → limite basse
    const SSID_ITEM_X: u16 = 45;
    const SSID_ITEM_W: u16 = 270;
    const SCROLL_BTN_H: u16 = 20;
    const SCROLL_TOP_Y: u16 = 60;
    const SCROLL_BOTTOM_Y: u16 = 300;

    // Calculer le nombre d'items qui peuvent tenir
    let available_h = SSID_MAX_Y - SSID_ORIGIN_Y;
    let max_visible_items = (available_h / (SSID_ITEM_H + SSID_ITEM_GAP)) as usize;

    let mut scroll_offset: usize = 0;

    // Fonction pour redessiner la liste
    let render_list = |lcd: &mut LcdDisplay, offset: usize| -> Result<()> {
        // Effacer la zone de liste
        lcd.fill_rect(SSID_ITEM_X, SSID_ORIGIN_Y, SSID_ITEM_W, SSID_MAX_Y - SSID_ORIGIN_Y, COLOR_BLACK)?;

        // Bouton SCROLL UP (en haut)
        if offset > 0 {
            // Bouton bleu : largeur complète 360px
            lcd.fill_rect(0, SCROLL_TOP_Y, 360, SCROLL_BTN_H, COLOR_BLUE)?;
            // Flèche haut bien visible (grande, blanche, centrée horizontalement à x=180)
            draw_text_lg(lcd, "^", 175, SCROLL_TOP_Y as i32 + 2, EG_WHITE)?;
        } else {
            // Pas de scroll possible : remplir en noir
            lcd.fill_rect(0, SCROLL_TOP_Y, 360, SCROLL_BTN_H, COLOR_BLACK)?;
        }

        // Afficher les items visibles
        let mut display_count = 0;
        for (i, ssid) in ssids.iter().enumerate() {
            if i < offset {
                continue;  // Skip les items au-dessus du scroll
            }
            if display_count >= max_visible_items {
                break;  // Stop si on dépasse la zone visible
            }

            let ry = SSID_ORIGIN_Y + display_count as u16 * (SSID_ITEM_H + SSID_ITEM_GAP);
            lcd.fill_rect(SSID_ITEM_X, ry, SSID_ITEM_W, SSID_ITEM_H - 2, COLOR_GRAY)?;
            let text_y = ry as i32 + 18;
            draw_text(lcd, ssid, SSID_ITEM_X as i32 + 10, text_y)?;
            let item_num = i + 1;  // 1-indexed
            info!("  SSID[{}]: {}", item_num, ssid);

            display_count += 1;
        }

        // Bouton SCROLL DOWN (en bas)
        if offset + max_visible_items < ssids.len() {
            // Bouton bleu : largeur complète 360px
            lcd.fill_rect(0, SCROLL_BOTTOM_Y, 360, SCROLL_BTN_H, COLOR_BLUE)?;
            // Flèche bas bien visible (grande, blanche, centrée horizontalement à x=180)
            draw_text_lg(lcd, "v", 175, SCROLL_BOTTOM_Y as i32 + 2, EG_WHITE)?;
        } else {
            // Pas de scroll possible : remplir en noir
            lcd.fill_rect(0, SCROLL_BOTTOM_Y, 360, SCROLL_BTN_H, COLOR_BLACK)?;
        }

        Ok(())
    };

    // Afficher la liste initiale
    render_list(lcd, scroll_offset)?;

    // --- Attente tap sur un SSID ---
    let selected_ssid = loop {
        if let Some(p) = lcd.read_touch() {
            // Zone scroll up (alignée sur le bouton haut)
            if p.y >= SCROLL_TOP_Y && p.y < SCROLL_TOP_Y + SCROLL_BTN_H && scroll_offset > 0 {
                scroll_offset -= 1;
                render_list(lcd, scroll_offset)?;
                FreeRtos::delay_ms(150);  // anti-rebond
                continue;
            }

            // Zone scroll down (alignée sur le bouton bas)
            if p.y >= SCROLL_BOTTOM_Y && p.y < SCROLL_BOTTOM_Y + SCROLL_BTN_H && scroll_offset + max_visible_items < ssids.len() {
                scroll_offset += 1;
                render_list(lcd, scroll_offset)?;
                FreeRtos::delay_ms(150);  // anti-rebond
                continue;
            }

            // Zone de sélection SSID
            if p.y >= SSID_ORIGIN_Y && p.y <= SSID_MAX_Y && p.x >= SSID_ITEM_X && p.x < SSID_ITEM_X + SSID_ITEM_W {
                let idx_in_view = ((p.y - SSID_ORIGIN_Y) / (SSID_ITEM_H + SSID_ITEM_GAP)) as usize;
                let global_idx = scroll_offset + idx_in_view;

                if global_idx < ssids.len() {
                    let ry = SSID_ORIGIN_Y + idx_in_view as u16 * (SSID_ITEM_H + SSID_ITEM_GAP);
                    lcd.fill_rect(SSID_ITEM_X, ry, SSID_ITEM_W, SSID_ITEM_H - 2, COLOR_GREEN)?;
                    FreeRtos::delay_ms(300);
                    info!("UI: SSID sélectionné: {} (index {})", ssids[global_idx], global_idx);
                    break ssids[global_idx];
                }
            }
        }
        FreeRtos::delay_ms(50);
    };

    // --- Saisie mot de passe ---
    lcd.fill(COLOR_BLACK)?;
    draw_password_screen(lcd, selected_ssid, "", false)?;
    let mut kb_mode = KeyboardMode::Letters;
    keyboard_draw(lcd, kb_mode)?;

    let mut password: HString<64> = HString::new();
    let mut reveal_last_until_us: i64 = 0;

    let mut confirmed_password: Option<HString<64>> = None;

    loop {
        if reveal_last_until_us > 0 && now_us() >= reveal_last_until_us {
            reveal_last_until_us = 0;
            draw_password_field(lcd, password.as_str(), false)?;
        }

        if let Some(p) = lcd.read_touch() {
            if is_back_touch(p, BACK_BTN_RIGHT_X, BACK_BTN_PASS_Y) {
                FreeRtos::delay_ms(150);  // anti-rebond
                continue 'provision;
            }

            match keyboard_flash_pressed(lcd, p, kb_mode)? {
                KeyPress::Confirm => {
                    info!("UI: Mot de passe confirmé ({} car.)", password.len());
                    confirmed_password = Some(password.clone());
                    break;
                }
                KeyPress::ModeSwitch => {
                    kb_mode = next_mode(kb_mode);
                    keyboard_draw(lcd, kb_mode)?;
                }
                KeyPress::Backspace => {
                    if !password.is_empty() {
                        let new_len = password.len() - 1;
                        password.truncate(new_len);
                    }
                    reveal_last_until_us = 0;
                    draw_password_screen(lcd, selected_ssid, password.as_str(), false)?;
                }
                KeyPress::Char(c) => {
                    let _ = password.push(c);
                    reveal_last_until_us = now_us() + 700_000;
                    draw_password_field(lcd, password.as_str(), true)?;
                }
                KeyPress::None => {}
            }
            FreeRtos::delay_ms(150);  // anti-rebond
        }
        FreeRtos::delay_ms(50);
    }

    let mut selected: HString<32> = HString::new();
    for c in selected_ssid.chars() {
        let _ = selected.push(c);
    }

    let Some(confirmed_password) = confirmed_password else {
        continue 'provision;
    };

    return Ok((selected, confirmed_password));
    }
}
