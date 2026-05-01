use edge_base::{Config, Runtime, process_transcript};

fn main() {
    let config = Config::new("nova");
    let mut runtime = Runtime::new(&config);

    let transcript = "nova allume la lumiere";
    let decision = process_transcript(&mut runtime, &config, transcript);

    println!(
        "result={:?} should_send={} command={:?}",
        decision.result, decision.should_send, decision.command
    );

    if decision.should_send {
        println!("Command: {}", decision.command.unwrap_or(""));
    }

    assert!(decision.should_send);
}
