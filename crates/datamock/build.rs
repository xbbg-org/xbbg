use std::env;
use std::path::PathBuf;

fn main() {
    let cpp_dir = PathBuf::from("cpp");
    let src_dir = cpp_dir.join("src");
    let include_dir = cpp_dir.join("include").join("datamock");

    // Collect all .cpp files
    let sources: Vec<PathBuf> = glob::glob(src_dir.join("**/*.cpp").to_str().unwrap())
        .expect("Failed to read glob pattern")
        .filter_map(Result::ok)
        .collect();

    if sources.is_empty() {
        println!("cargo:warning=No C++ source files found in cpp/src/");
        return;
    }

    let mut build = cc::Build::new();

    // Parent include dir for #include "datamock/..."
    let include_parent = cpp_dir.join("include");

    build
        .cpp(true)
        .std("c++17")
        .include(&include_dir)
        .include(&include_parent)
        // Include the src directory for internal headers
        .include(&src_dir)
        // Define DATAMOCK_BUILDING for DLL export macros
        .define("DATAMOCK_BUILDING", None);

    // Platform-specific settings
    if cfg!(target_os = "windows") {
        build
            .define("_WIN32_WINNT", "0x0601")
            .define("NOMINMAX", None);
    }

    // Add warning flags (similar to CMake setup)
    if cfg!(not(target_env = "msvc")) {
        build.flag("-Wall").flag("-Wextra").flag("-Wpedantic");
    }

    // Add all source files
    for source in &sources {
        build.file(source);
        // Tell Cargo to rerun if source files change
        println!("cargo:rerun-if-changed={}", source.display());
    }

    // Rerun if headers change
    println!("cargo:rerun-if-changed=cpp/include");
    println!("cargo:rerun-if-changed=cpp/src");

    build.compile("datamock");

    // Link threading library on Unix
    if cfg!(target_family = "unix") {
        println!("cargo:rustc-link-lib=pthread");
    }

    // Generate Rust bindings from the C API header
    let bindings = bindgen::Builder::default()
        .header("cpp/include/datamock/datamock_c_api.h")
        .clang_arg("-DDATAMOCK_EXPORT=")
        .parse_callbacks(Box::new(bindgen::CargoCallbacks::new()))
        .generate()
        .expect("Unable to generate bindings");

    let out_path = PathBuf::from(env::var("OUT_DIR").unwrap());
    bindings
        .write_to_file(out_path.join("bindings.rs"))
        .expect("Couldn't write bindings!");
}
