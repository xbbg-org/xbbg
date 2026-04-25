fn main() {
    // No build script work is required here; blpapi-sys owns binding generation.
    println!("cargo:rerun-if-changed=build.rs");
}
