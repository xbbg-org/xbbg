use std::env;
use std::fs;
use std::path::{Path, PathBuf};

fn main() {
    // Ensure rebuilds when env changes
    println!("cargo:rerun-if-env-changed=BLPAPI_INCLUDE_DIR");
    println!("cargo:rerun-if-env-changed=BLPAPI_LIB_DIR");
    println!("cargo:rerun-if-env-changed=BLPAPI_ROOT");
    println!("cargo:rerun-if-env-changed=XBBG_DEV_SDK_ROOT");
    println!("cargo:rerun-if-env-changed=BLPAPI_LINK_LIB_NAME");

    // Resolve include and lib directories from environment (precedence order)
    let (include_dir, lib_dir) =
        resolve_include_and_lib_dirs().unwrap_or_else(|e| panic!("blpapi-sys: {}", e));

    // Emit link search path
    println!("cargo:rustc-link-search=native={}", lib_dir.display());

    // Enforce mutually exclusive static/dynamic features
    let want_static = env::var_os("CARGO_FEATURE_STATIC").is_some();
    let want_dynamic = env::var_os("CARGO_FEATURE_DYNAMIC").is_some() || !want_static;
    if want_static && want_dynamic {
        panic!("Features 'static' and 'dynamic' are mutually exclusive");
    }

    // Determine library base name based on target platform and architecture
    let lib_name = env::var("BLPAPI_LINK_LIB_NAME").ok().unwrap_or_else(|| {
        let target_os = env::var("CARGO_CFG_TARGET_OS").unwrap_or_default();
        let target_arch = env::var("CARGO_CFG_TARGET_ARCH").unwrap_or_default();

        if target_os == "windows" {
            if target_arch == "x86" {
                "blpapi3_32".to_string()
            } else {
                "blpapi3_64".to_string()
            }
        } else {
            // Linux uses blpapi3 (symlinked from blpapi3_64)
            "blpapi3".to_string()
        }
    });

    // Emit link type
    if want_static {
        println!("cargo:rustc-link-lib=static={}", lib_name);
    } else {
        println!("cargo:rustc-link-lib=dylib={}", lib_name);
    }

    // Build bindgen wrapper that includes all blpapi_*.h headers found
    let wrapper =
        generate_wrapper_header(&include_dir).unwrap_or_else(|e| panic!("blpapi-sys: {}", e));

    // Prepare bindgen
    let out_dir = PathBuf::from(env::var("OUT_DIR").expect("OUT_DIR not set"));
    let bindings_out = out_dir.join("bindings.rs");

    let builder = bindgen::Builder::default()
        .header_contents("wrapper.h", &wrapper)
        .clang_arg(format!("-I{}", include_dir.display()))
        .allowlist_function("^blpapi_.*")
        .allowlist_type("^blpapi_.*")
        .allowlist_var("^(BLPAPI_.*|BLPAPI_SDK_VERSION.*|g_blpapi.*)")
        .ctypes_prefix("cty")
        .use_core()
        .layout_tests(false)
        .derive_default(false)
        .generate_comments(false)
        .formatter(bindgen::Formatter::Rustfmt);

    // Generate and write
    let bindings = builder
        .generate()
        .expect("Unable to generate blpapi bindings via bindgen");

    bindings
        .write_to_file(&bindings_out)
        .unwrap_or_else(|e| panic!("Failed to write bindings: {}", e));

    // Compile C shim for CorrelationId helpers
    println!("cargo:rerun-if-changed=src/xb_ext.c");
    cc::Build::new()
        .file("src/xb_ext.c")
        .include(&include_dir)
        .warnings(false)
        .compile("blpapiext_cid");
}

fn resolve_include_and_lib_dirs() -> Result<(PathBuf, PathBuf), String> {
    // 1) Explicit include/lib
    let include = env::var_os("BLPAPI_INCLUDE_DIR");
    let lib = env::var_os("BLPAPI_LIB_DIR");
    if let (Some(inc), Some(lib)) = (include, lib) {
        let inc = PathBuf::from(inc);
        let lib = PathBuf::from(lib);
        validate_header_exists(&inc)?;
        return Ok((inc, lib));
    }

    // 2) Root
    if let Some(root) = env::var_os("BLPAPI_ROOT") {
        let root = PathBuf::from(root);
        let (inc, lib) = derive_include_lib(&root)?;
        validate_header_exists(&inc)?;
        return Ok((inc, lib));
    }

    // 3) Dev-only SDK root
    if let Some(root) = env::var_os("XBBG_DEV_SDK_ROOT") {
        let root = PathBuf::from(root);
        let (inc, lib) = derive_include_lib(&root)?;
        validate_header_exists(&inc)?;
        return Ok((inc, lib));
    }

    Err("Cannot locate Bloomberg SDK. Set BLPAPI_INCLUDE_DIR/BLPAPI_LIB_DIR, or BLPAPI_ROOT, or XBBG_DEV_SDK_ROOT".into())
}

fn derive_include_lib(root: &Path) -> Result<(PathBuf, PathBuf), String> {
    let inc = root.join("include");
    let target_arch = env::var("CARGO_CFG_TARGET_ARCH").unwrap_or_default();

    // Try common layouts:
    // <root>/include and <root>/lib
    let lib1 = root.join("lib");
    if inc.is_dir() && lib1.is_dir() {
        return Ok((inc, lib1));
    }

    // Windows: check architecture-specific lib directories
    let win_lib_subdir = if target_arch == "x86" {
        "win32"
    } else {
        "win64"
    };
    let lib2 = root.join("lib").join(win_lib_subdir);
    if inc.is_dir() && lib2.is_dir() {
        return Ok((inc, lib2));
    }

    // Fallback: try capitalized Include/Lib (rare)
    let inc3 = root.join("Include");
    let lib3 = root.join("Lib");
    if inc3.is_dir() && lib3.is_dir() {
        return Ok((inc3, lib3));
    }

    Err(format!(
        "Could not derive include/lib under {}. Expected include/ and lib/ (or lib/{win_lib_subdir}/).",
        root.display()
    ))
}

fn validate_header_exists(include_dir: &Path) -> Result<(), String> {
    let candidates = [
        "blpapi_session.h",
        "blpapi_defs.h",
        "blpapi_types.h",
        "blpapi_name.h",
    ];
    let ok = candidates.iter().any(|h| include_dir.join(h).is_file());
    if ok {
        Ok(())
    } else {
        Err(format!(
            "Could not find expected Bloomberg headers in {}",
            include_dir.display()
        ))
    }
}

fn generate_wrapper_header(include_dir: &Path) -> Result<String, String> {
    let mut headers: Vec<String> = Vec::new();
    for entry in fs::read_dir(include_dir).map_err(|e| e.to_string())? {
        let entry = entry.map_err(|e| e.to_string())?;
        let path = entry.path();
        if let (Some(stem), Some(ext)) = (path.file_name(), path.extension()) {
            if ext == "h" {
                let name = stem.to_string_lossy().to_string();
                if name.starts_with("blpapi_") {
                    headers.push(format!("#include <{}>", stem.to_string_lossy()));
                }
            }
        }
    }
    if headers.is_empty() {
        return Err(format!(
            "No blpapi_*.h headers found in {}",
            include_dir.display()
        ));
    }
    headers.sort();
    let mut out = String::new();
    out.push_str("/* auto-generated wrapper for bindgen */\n");
    for line in headers {
        out.push_str(&line);
        out.push('\n');
    }
    Ok(out)
}
