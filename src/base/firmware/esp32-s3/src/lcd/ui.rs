/// lcd/ui.rs — Écrans applicatifs (provisioning WiFi, statut, clavier tactile)

use super::{LcdDisplay, TouchPoint, COLOR_BLACK, COLOR_BLUE, COLOR_GRAY, COLOR_GREEN,
            COLOR_ORANGE, COLOR_RED, COLOR_WHITE, LCD_W, LCD_H};
use anyhow::Result;
use esp_idf_hal::delay::FreeRtos;
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

/// Affiche une ligne de texte en grand (10×20).
fn draw_text_lg(lcd: &mut LcdDisplay, text: &str, x: i32, y: i32, color: Rgb565) -> Result<()> {
    let style = MonoTextStyle::new(&FONT_10X20, color);
    Text::new(text, Point::new(x, y), style).draw(lcd)?;
    Ok(())
}

// ----------------------------------------------------------------
// Clavier tactile minimal
// Disposition : 5 rangées, 10 colonnes (minuscules + chiffres + _-@.)
// Rangée 4 : BKSP (¾ largeur) + OK (¼ largeur)
// ----------------------------------------------------------------

const KB_ROWS: usize = 5;
const KB_COLS: usize = 10;
const KB_KEY_W: u16 = 24;
const KB_KEY_H: u16 = 28;
const KB_KEY_GAP: u16 = 2;
const KB_ORIGIN_Y: u16 = 140;

static KB_LAYOUT: [&[u8; 10]; 4] = [
    b"1234567890",
    b"qwertyuiop",
    b"asdfghjkl_",
    b"zxcvbnm-@.",
];

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum KeyPress {
    Char(char),
    Backspace,
    Confirm,
    None,
}

pub fn keyboard_hit_test(p: TouchPoint) -> KeyPress {
    if p.y < KB_ORIGIN_Y {
        return KeyPress::None;
    }
    let row = ((p.y - KB_ORIGIN_Y) / (KB_KEY_H + KB_KEY_GAP)) as usize;
    if row >= KB_ROWS {
        return KeyPress::None;
    }
    // Rangée spéciale (4) : BKSP + OK
    if row == 4 {
        let bksp_w = LCD_W * 3 / 4;
        return if p.x < bksp_w { KeyPress::Backspace } else { KeyPress::Confirm };
    }
    let col = (p.x / (KB_KEY_W + KB_KEY_GAP)) as usize;
    if col >= KB_COLS {
        return KeyPress::None;
    }
    KeyPress::Char(KB_LAYOUT[row][col] as char)
}

pub fn keyboard_draw(lcd: &mut LcdDisplay) -> Result<()> {
    lcd.fill_rect(0, KB_ORIGIN_Y, LCD_W, LCD_H - KB_ORIGIN_Y, COLOR_GRAY)?;
    for row in 0..KB_ROWS - 1 {
        for col in 0..KB_COLS {
            let kx = col as u16 * (KB_KEY_W + KB_KEY_GAP);
            let ky = KB_ORIGIN_Y + row as u16 * (KB_KEY_H + KB_KEY_GAP);
            lcd.fill_rect(kx + 1, ky + 1, KB_KEY_W - 2, KB_KEY_H - 2, COLOR_WHITE)?;
        }
    }
    // Rangée spéciale
    let bksp_w = LCD_W * 3 / 4;
    let ok_w = LCD_W - bksp_w;
    let ky = KB_ORIGIN_Y + 4 * (KB_KEY_H + KB_KEY_GAP);
    lcd.fill_rect(1, ky + 1, bksp_w - 2, KB_KEY_H - 2, COLOR_ORANGE)?;
    lcd.fill_rect(bksp_w + 1, ky + 1, ok_w - 2, KB_KEY_H - 2, COLOR_GREEN)?;
    Ok(())
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

    // --- Affichage liste SSIDs avec scroll ---
    // Zone circulaire : x=50..310 (w=260) est sûre pour y=65..295
    lcd.fill(COLOR_BLACK)?;
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
    const SCROLL_ZONE_H: u16 = 15;   // zone haut/bas pour scroll

    // Calculer le nombre d'items qui peuvent tenir
    let available_h = SSID_MAX_Y - SSID_ORIGIN_Y;
    let max_visible_items = (available_h / (SSID_ITEM_H + SSID_ITEM_GAP)) as usize;

    let mut scroll_offset: usize = 0;

    // Fonction pour redessiner la liste
    let render_list = |lcd: &mut LcdDisplay, offset: usize| -> Result<()> {
        // Effacer la zone de liste
        lcd.fill_rect(SSID_ITEM_X, SSID_ORIGIN_Y, SSID_ITEM_W, SSID_MAX_Y - SSID_ORIGIN_Y, COLOR_BLACK)?;

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

        // Afficher les indicateurs de scroll
        if offset > 0 {
            // Flèche haut (↑) — juste après le séparateur
            draw_text(lcd, "^", 170, 86)?;
        }
        if offset + max_visible_items < ssids.len() {
            // Flèche bas (↓)
            draw_text(lcd, "v", 170, 285)?;
        }

        Ok(())
    };

    // Afficher la liste initiale
    render_list(lcd, scroll_offset)?;

    // --- Attente tap sur un SSID ---
    let selected_ssid = loop {
        if let Some(p) = lcd.read_touch() {
            // Zone scroll up
            if p.y < SCROLL_ZONE_H && scroll_offset > 0 {
                scroll_offset -= 1;
                render_list(lcd, scroll_offset)?;
                FreeRtos::delay_ms(150);  // anti-rebond
                continue;
            }

            // Zone scroll down
            if p.y > SSID_MAX_Y && scroll_offset + max_visible_items < ssids.len() {
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
    lcd.draw_banner(0, 18, COLOR_BLUE)?;
    keyboard_draw(lcd)?;

    let mut password: HString<64> = HString::new();

    let confirmed_password = loop {
        if let Some(p) = lcd.read_touch() {
            match keyboard_hit_test(p) {
                KeyPress::Confirm => {
                    info!("UI: Mot de passe confirmé ({} car.)", password.len());
                    break password.clone();
                }
                KeyPress::Backspace => {
                    if !password.is_empty() {
                        let new_len = password.len() - 1;
                        password.truncate(new_len);
                    }
                    keyboard_draw(lcd)?;
                }
                KeyPress::Char(c) => {
                    let _ = password.push(c);
                    keyboard_draw(lcd)?;
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

    Ok((selected, confirmed_password))
}
