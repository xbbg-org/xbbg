//! Build script to embed git version information.
//!
//! This emits `VERGEN_GIT_DESCRIBE` with the output of `git describe --tags --dirty --always`,
//! giving us versions like:
//! - `v1.0.0` (on a tag)
//! - `v1.0.0-5-g1a2b3c4` (5 commits after tag)

use std::process::Command;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("cargo:rerun-if-changed=.git/HEAD");
    println!("cargo:rerun-if-changed=.git/refs");

    let git_describe = Command::new("git")
        .args(["describe", "--tags", "--dirty", "--always"])
        .output()
        .ok()
        .filter(|out| out.status.success())
        .map(|out| String::from_utf8_lossy(&out.stdout).trim().to_string())
        .filter(|value| !value.is_empty())
        .unwrap_or_else(|| "unknown".to_string());

    println!("cargo:rustc-env=VERGEN_GIT_DESCRIBE={git_describe}");

    Ok(())
}
