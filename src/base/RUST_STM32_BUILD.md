# Rust Firmware for STM32 Edge Base

## Prerequis

- Rust toolchain (rustup): https://rustup.rs/
- ARM target: `rustup target add thumbv7em-none-eabihf`
- Optional: arm-none-eabi tools for flashing

## Build sur hote (test + exemple)

```bash
cd src/base/firmware/stm32-rust
cargo build --release --example example --features std
cargo test --lib --features std
cargo test --test integration_tests --features std
```

## Build cross-compile STM32 (bare-metal)

```bash
cd src/base/firmware/stm32-rust
rustup target add thumbv7em-none-eabihf
cargo build --release --target thumbv7em-none-eabihf
```

ou pour d'autres MCU:

```
# STM32L4
cargo build --release --target thumbv7em-none-eabihf --features stm32l4

# STM32H7xx (Cortex-M7)
rustup target add thumbv7em-none-eabihf
cargo build --release --target thumbv7em-none-eabihf
```

## Structure

- `src/lib.rs`: coeur runtime (structures, logique)
- `examples/main.rs`: exemple d'utilisation
- `tests/integration_tests.rs`: tests d'intégration
- `Cargo.toml`: dependances et configuration

## Avantages Rust vs C

- Sécurité mémoire garantie à la compilation (pas de buffer overflow, use-after-free)
- Gestion automatique des ressources (RAII)
- Zéro overhead runtime
- Meilleure ergonomie de l'API
- Tests intégrés au compilateur

## Exemple de code

```rust
use edge_base::{Config, Runtime, process_transcript};

let config = Config::new("nova");
let mut runtime = Runtime::new(&config);

let decision = process_transcript(&mut runtime, &config, "nova allume la lumiere");
if decision.should_send {
    println!("Command: {}", decision.command.unwrap());
}
```

## Prochaines étapes

- Ajouter support STM32 HAL (stm32l4xx-hal, stm32h7xx-hal)
- Intégrer I2S audio capture 
- Ajouter transport réseau (socket Ethernet/WiFi)
- Tests matériel sur cible réelle
