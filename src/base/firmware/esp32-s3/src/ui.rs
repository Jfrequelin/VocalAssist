/// ui.rs — Écrans applicatifs (provisioning WiFi, statut, clavier tactile)

#[allow(unused_imports)] // couleurs utilisées dans le binaire, absentes du harness de test
use crate::lcd::{LcdDisplay, TouchPoint,
    COLOR_BLACK, COLOR_BLUE, COLOR_GRAY, COLOR_GREEN, COLOR_ORANGE, COLOR_RED, COLOR_WHITE,
    LCD_W, LCD_H};
use anyhow::Result;
use esp_idf_hal::delay::FreeRtos;
use esp_idf_sys::esp_timer_get_time;
use heapless;
use log::info;

use embedded_graphics::{
    mono_font::{ascii::{FONT_9X15, FONT_10X20}, MonoTextStyle},
    pixelcolor::Rgb565,
    prelude::*,
    primitives::{Circle, PrimitiveStyleBuilder},
    text::Text,
};

// Couleurs embedded-graphics (correspondance avec les u16 existants)
const EG_WHITE:  Rgb565 = Rgb565::new(31, 63, 31);
const EG_BLACK:  Rgb565 = Rgb565::new(0, 0, 0);
const EG_BLUE:   Rgb565 = Rgb565::new(0, 0, 31);
const EG_GREEN:  Rgb565 = Rgb565::new(0, 63, 0);
const EG_RED:    Rgb565 = Rgb565::new(31, 0, 0);
const EG_ORANGE: Rgb565 = Rgb565::new(31, 41, 0);
const EG_CYAN:   Rgb565 = Rgb565::new(0, 50, 31);
const EG_GRAY:   Rgb565 = Rgb565::new(12, 24, 12);

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

pub fn show_server_unreachable(lcd: &mut LcdDisplay) -> Result<()> {
    lcd.fill(COLOR_BLACK)?;
    lcd.fill_rect(50, 140, 260, 40, COLOR_RED)?;
    draw_text_lg(lcd, "Serveur KO", 100, 166, EG_WHITE)?;
    draw_text(lcd, "Injoignable", 110, 195)?;
    info!("UI: Serveur injoignable ✗");
    Ok(())
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

    let confirmed_password: HString<64> = loop {
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
                    break password.clone();
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
    };

    let mut selected: HString<32> = HString::new();
    for c in selected_ssid.chars() {
        let _ = selected.push(c);
    }

    return Ok((selected, confirmed_password));
    }
}

// ================================================================
// Écran Config HA
// ================================================================

/// Dessine le cadre + contenu d'un champ de saisie texte générique.
fn draw_field_content(lcd: &mut LcdDisplay, label: &str, value: &str) -> Result<()> {
    // Titre du label
    lcd.fill_rect(0, 58, LCD_W, 18, COLOR_BLACK)?;
    draw_text(lcd, label, 20, 74)?;
    // Cadre + contenu
    lcd.fill_rect(20, 78, LCD_W - 40, 44, COLOR_WHITE)?;
    lcd.fill_rect(22, 80, LCD_W - 44, 40, COLOR_BLACK)?;
    // Valeur (tronquée à 38 chars pour tenir sur l'écran)
    let mut line: heapless::String<48> = heapless::String::new();
    for c in value.chars().take(38) { let _ = line.push(c); }
    draw_text_color(lcd, line.as_str(), 28, 106, EG_GREEN)?;
    Ok(())
}

/// Saisit un champ texte via le clavier tactile.
/// `title` : titre (ex. "Config HA 1/2"), `label` : libellé du champ.
/// `initial` : valeur initiale affichée. `kb_init` : mode clavier initial.
/// Retourne `Some(valeur)` si confirmé, `None` si annulé (back).
fn run_text_field_screen(
    lcd: &mut LcdDisplay,
    title: &str,
    label: &str,
    initial: &str,
    kb_init: KeyboardMode,
) -> Result<Option<heapless::String<64>>> {
    let mut value: heapless::String<64> = heapless::String::new();
    for c in initial.chars().take(63) { let _ = value.push(c); }

    // Dessiner l'écran complet
    lcd.fill(COLOR_BLACK)?;
    lcd.draw_banner(0, 32, COLOR_BLUE)?;
    draw_text_lg(lcd, title, 20, 24, EG_WHITE)?;
    draw_back_button(lcd, BACK_BTN_RIGHT_X, BACK_BTN_PASS_Y)?;
    draw_field_content(lcd, label, value.as_str())?;
    let mut kb_mode = kb_init;
    keyboard_draw(lcd, kb_mode)?;

    loop {
        if let Some(p) = lcd.read_touch() {
            if is_back_touch(p, BACK_BTN_RIGHT_X, BACK_BTN_PASS_Y) {
                FreeRtos::delay_ms(150);
                return Ok(None);
            }
            match keyboard_flash_pressed(lcd, p, kb_mode)? {
                KeyPress::Confirm => {
                    info!("UI: champ confirmé ({} car.)", value.len());
                    return Ok(Some(value));
                }
                KeyPress::ModeSwitch => {
                    kb_mode = next_mode(kb_mode);
                    keyboard_draw(lcd, kb_mode)?;
                }
                KeyPress::Backspace => {
                    if !value.is_empty() {
                        let new_len = value.len() - 1;
                        value.truncate(new_len);
                    }
                    draw_field_content(lcd, label, value.as_str())?;
                }
                KeyPress::Char(c) => {
                    let _ = value.push(c);
                    draw_field_content(lcd, label, value.as_str())?;
                }
                KeyPress::None => {}
            }
            FreeRtos::delay_ms(150);
        }
        FreeRtos::delay_ms(50);
    }
}

/// Saisir la configuration HA : host IP et port.
/// Retourne `(host, port)` après confirmation (ou valeurs inchangées si annulé).
pub fn run_ha_config(
    lcd: &mut LcdDisplay,
    current_host: &str,
    current_port: u16,
) -> Result<(heapless::String<64>, u16)> {
    // Étape 1 — Host
    let host = match run_text_field_screen(
        lcd,
        "Config HA 1/2",
        "Host IP:",
        current_host,
        KeyboardMode::Numbers,
    )? {
        Some(h) if !h.is_empty() => h,
        _ => {
            // Annulé — retourner les valeurs actuelles
            let mut h: heapless::String<64> = heapless::String::new();
            for c in current_host.chars().take(63) { let _ = h.push(c); }
            return Ok((h, current_port));
        }
    };

    // Étape 2 — Port
    let mut port_str: heapless::String<8> = heapless::String::new();
    let _ = core::fmt::write(&mut port_str, format_args!("{}", current_port));
    let port = match run_text_field_screen(
        lcd,
        "Config HA 2/2",
        "Port (8123):",
        port_str.as_str(),
        KeyboardMode::Numbers,
    )? {
        Some(s) => s.as_str().parse::<u16>().unwrap_or(current_port),
        None => current_port,
    };

    Ok((host, port))
}

// ================================================================
// Écran READY — Phase 1
// ================================================================

/// État de l'appareil affiché sur l'écran READY.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum DeviceState {
    Idle,
    Listening,
    Thinking,
    Speaking,
    #[allow(dead_code)]
    Error,
}

/// Action retournée par [`run_ready_loop`].
pub enum ReadyAction {
    StartListening,
    ConfigHa,
}

// --- Géométrie ---
const READY_CENTER_X:  i32 = 180;
const READY_CENTER_Y:  i32 = 170;
const READY_RADIUS:    u32 = 78;
const READY_LABEL_Y:   i32 = 272;
const READY_HINT_Y:    i32 = 308;

fn state_eg_color(state: DeviceState) -> Rgb565 {
    match state {
        DeviceState::Idle      => EG_BLUE,
        DeviceState::Listening => EG_GREEN,
        DeviceState::Thinking  => EG_ORANGE,
        DeviceState::Speaking  => EG_CYAN,
        DeviceState::Error     => EG_RED,
    }
}

/// Retourne (texte, x centré) pour FONT_10X20 (10 px/char).
fn state_label(state: DeviceState) -> (&'static str, i32) {
    match state {
        DeviceState::Idle      => ("PRET",      160),
        DeviceState::Listening => ("EN ECOUTE", 115),
        DeviceState::Thinking  => ("REFLEXION", 115),
        DeviceState::Speaking  => ("PARLE",     155),
        DeviceState::Error     => ("ERREUR",    150),
    }
}

/// Dessine (ou rafraîchit partiellement) le disque coloré + texte d'état.
fn draw_state_indicator(lcd: &mut LcdDisplay, state: DeviceState) -> Result<()> {
    let d   = READY_RADIUS * 2;
    let tlx = READY_CENTER_X - READY_RADIUS as i32;
    let tly = READY_CENTER_Y - READY_RADIUS as i32;

    // Effacer zones (disque + label)
    lcd.fill_rect(tlx as u16, tly as u16, d as u16, d as u16, COLOR_BLACK)?;
    lcd.fill_rect(0, (READY_LABEL_Y - 16) as u16, LCD_W, 22, COLOR_BLACK)?;

    // Disque coloré (embedded-graphics Circle)
    let style = PrimitiveStyleBuilder::new()
        .fill_color(state_eg_color(state))
        .build();
    Circle::new(Point::new(tlx, tly), d)
        .into_styled(style)
        .draw(lcd)?;

    // Texte d'état centré sous le disque
    let (label, lx) = state_label(state);
    draw_text_lg(lcd, label, lx, READY_LABEL_Y, EG_WHITE)?;

    Ok(())
}

/// Barre de statut haut (WiFi + Serveur).
fn draw_ready_status_bar(lcd: &mut LcdDisplay, wifi_ok: bool, server_ok: bool) -> Result<()> {
    lcd.fill_rect(0, 0, LCD_W, 30, COLOR_BLACK)?;
    let wc = if wifi_ok  { EG_GREEN } else { EG_RED };
    let sc = if server_ok { EG_GREEN } else { EG_RED };
    draw_text_color(lcd, if wifi_ok  { "WiFi OK" } else { "WiFi KO" }, 10,  20, wc)?;
    draw_text_color(lcd, if server_ok { "Srv OK" } else { "Srv KO"  }, 272, 20, sc)?;
    Ok(())
}

/// Rendu complet de l'écran READY.
pub fn draw_ready_screen(
    lcd: &mut LcdDisplay,
    state: DeviceState,
    wifi_ok: bool,
    server_ok: bool,
) -> Result<()> {
    lcd.fill_rect(0, 0, LCD_W, LCD_H, COLOR_BLACK)?;
    draw_ready_status_bar(lcd, wifi_ok, server_ok)?;
    draw_state_indicator(lcd, state)?;
    draw_text_color(lcd, "Appuyer pour parler", 52, READY_HINT_Y, EG_GRAY)?;
    Ok(())
}

/// Met à jour uniquement l'indicateur d'état (redraw partiel, sans effacer tout l'écran).
pub fn update_ready_state(lcd: &mut LcdDisplay, state: DeviceState) -> Result<()> {
    draw_state_indicator(lcd, state)
}

/// Affiche la réponse texte du serveur sous le disque d'état.
///
/// Efface la zone de réponse puis affiche `answer` sur deux lignes si nécessaire.
/// Appelé après réception d'une réponse `/edge/audio`.
pub fn show_answer(lcd: &mut LcdDisplay, answer: &str, intent: &str) -> Result<()> {
    const ANSWER_Y: i32 = 50;  // y dans la zone haute (au-dessus du disque)
    const ANSWER_X: i32 = 10;
    const MAX_CHARS_PER_LINE: usize = 36;

    // Effacer la zone texte
    lcd.fill_rect(0, (ANSWER_Y - 16) as u16, LCD_W, 60, COLOR_BLACK)?;

    // Afficher l'intent (petit, gris)
    if !intent.is_empty() {
        let mut intent_line: heapless::String<72> = heapless::String::new();
        let _ = intent_line.push_str(">");
        for c in intent.chars().take(35) { let _ = intent_line.push(c); }
        draw_text_color(lcd, intent_line.as_str(), ANSWER_X, ANSWER_Y, EG_GRAY)?;
    }

    // Afficher la réponse (deux lignes max)
    let chars: heapless::Vec<char, 128> = answer.chars().take(128).collect();
    let total = chars.len();
    if total > 0 {
        let line1_end = MAX_CHARS_PER_LINE.min(total);
        let mut line1: heapless::String<40> = heapless::String::new();
        for c in chars.iter().take(line1_end) { let _ = line1.push(*c); }
        draw_text_color(lcd, line1.as_str(), ANSWER_X, ANSWER_Y + 18, EG_WHITE)?;

        if total > MAX_CHARS_PER_LINE {
            let mut line2: heapless::String<40> = heapless::String::new();
            for c in chars.iter().skip(MAX_CHARS_PER_LINE).take(MAX_CHARS_PER_LINE) {
                let _ = line2.push(*c);
            }
            if total > MAX_CHARS_PER_LINE * 2 {
                // Tronquer avec ...
                line2.truncate(line2.len().saturating_sub(3));
                let _ = line2.push_str("...");
            }
            draw_text_color(lcd, line2.as_str(), ANSWER_X, ANSWER_Y + 34, EG_WHITE)?;
        }
    }
    Ok(())
}

/// Boucle principale écran READY.
///
/// - Tap court (< 1 s) sur le disque central → [`ReadyAction::StartListening`]
/// - Long-press (≥ 1.5 s) n'importe où → [`ReadyAction::ConfigHa`]
pub fn run_ready_loop(
    lcd: &mut LcdDisplay,
    wifi_ok: bool,
    server_ok: bool,
) -> Result<ReadyAction> {
    draw_ready_screen(lcd, DeviceState::Idle, wifi_ok, server_ok)?;
    let mut touch_start_us: i64 = 0;
    loop {
        if let Some(_p) = lcd.read_touch() {
            if touch_start_us == 0 {
                touch_start_us = now_us();
            }
            let held_ms = (now_us() - touch_start_us) / 1_000;
            if held_ms >= 1_500 {
                // Long-press → Config HA
                info!("UI: long-press détecté → Config HA");
                return Ok(ReadyAction::ConfigHa);
            }
        } else {
            // Relâché
            if touch_start_us > 0 {
                let held_ms = (now_us() - touch_start_us) / 1_000;
                if held_ms < 1_500 {
                    // Tap court → écoute
                    update_ready_state(lcd, DeviceState::Listening)?;
                    FreeRtos::delay_ms(150);
                    return Ok(ReadyAction::StartListening);
                }
                touch_start_us = 0;
            }
        }
        FreeRtos::delay_ms(50);
    }
}

/// Sonde le tactile pendant `max_ms` ms au maximum.
///
/// `touch_state` persiste entre appels (0 = pas de touche en cours).
/// Retourne l'action détectée ou `None` si le timeout expire sans interaction.
/// N'actualise PAS l'écran — l'appelant est responsable de l'affichage.
pub fn poll_touch_quick(
    lcd: &mut LcdDisplay,
    _wifi_ok: bool,
    _server_ok: bool,
    max_ms: u32,
    touch_state: &mut i64,
) -> Result<Option<ReadyAction>> {
    let deadline_us = now_us() + (max_ms as i64) * 1_000;

    loop {
        if now_us() >= deadline_us {
            return Ok(None);
        }

        if let Some(_p) = lcd.read_touch() {
            if *touch_state == 0 {
                *touch_state = now_us();
            }
            let held_ms = (now_us() - *touch_state) / 1_000;
            if held_ms >= 1_500 {
                info!("UI: long-press → Config HA");
                *touch_state = 0;
                return Ok(Some(ReadyAction::ConfigHa));
            }
        } else if *touch_state > 0 {
            let held_ms = (now_us() - *touch_state) / 1_000;
            *touch_state = 0;
            if held_ms < 1_500 {
                update_ready_state(lcd, DeviceState::Listening)?;
                FreeRtos::delay_ms(150);
                return Ok(Some(ReadyAction::StartListening));
            }
        }

        FreeRtos::delay_ms(50);
    }
}
