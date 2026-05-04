// build.rs — requis par embuild pour injecter les variables ESP-IDF (IDF_PATH, etc.)
fn main() {
    embuild::espidf::sysenv::output();
}
