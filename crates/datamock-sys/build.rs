use std::env;
use std::path::PathBuf;

fn main() {
    // Path to datamock crate (sibling directory)
    let manifest_dir = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap());
    let datamock_dir = manifest_dir.parent().unwrap().join("datamock");
    let include_dir = datamock_dir.join("cpp").join("include");
    let header_path = include_dir.join("datamock").join("datamock_c_api.h");

    // Rerun if header changes
    println!("cargo:rerun-if-changed={}", header_path.display());

    // Link to the datamock library (built by datamock crate)
    // The datamock crate compiles to libdatamock.a via cc crate
    let out_dir = PathBuf::from(env::var("OUT_DIR").unwrap());

    // Find the datamock library in the target directory
    // The datamock crate builds to target/{profile}/build/datamock-{hash}/out/
    let target_dir = out_dir
        .ancestors()
        .find(|p| p.ends_with("build"))
        .and_then(|p| p.parent())
        .unwrap_or(&out_dir);

    // Search for datamock library in build outputs
    for entry in std::fs::read_dir(target_dir.join("build"))
        .into_iter()
        .flatten()
    {
        if let Ok(entry) = entry {
            let name = entry.file_name();
            if name.to_string_lossy().starts_with("datamock-") {
                let lib_dir = entry.path().join("out");
                if lib_dir.exists() {
                    println!("cargo:rustc-link-search=native={}", lib_dir.display());
                }
            }
        }
    }

    println!("cargo:rustc-link-lib=static=datamock");

    // On Windows, link C++ runtime
    if cfg!(target_os = "windows") {
        // MSVC links C++ runtime automatically
    } else {
        println!("cargo:rustc-link-lib=stdc++");
    }

    // Generate bindings with bindgen
    let bindings = bindgen::Builder::default()
        .header(header_path.to_str().unwrap())
        .clang_arg(format!("-I{}", include_dir.display()))
        .allowlist_function("^datamock_.*")
        .allowlist_type("^datamock_.*")
        .allowlist_var("^DATAMOCK_.*")
        .ctypes_prefix("cty")
        .use_core()
        .layout_tests(false)
        .derive_default(false)
        .generate_comments(false)
        .formatter(bindgen::Formatter::Rustfmt)
        .generate()
        .expect("Unable to generate datamock bindings");

    // Write bindings to OUT_DIR
    let bindings_out = out_dir.join("bindings.rs");
    bindings
        .write_to_file(&bindings_out)
        .expect("Failed to write bindings");
}
