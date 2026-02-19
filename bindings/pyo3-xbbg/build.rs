//! Build script to embed git version information via vergen.
//!
//! This emits `VERGEN_GIT_DESCRIBE` which contains the output of `git describe --tags`,
//! giving us versions like:
//! - `v1.0.0` (on a tag)
//! - `v1.0.0-5-g1a2b3c4` (5 commits after tag)

use vergen_gitcl::{BuildBuilder, CargoBuilder, Emitter, GitclBuilder};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let build = BuildBuilder::default().build_timestamp(true).build()?;
    let cargo = CargoBuilder::default().build()?;
    let gitcl = GitclBuilder::default()
        .describe(true, true, None) // tags=true, dirty=true
        .build()?;

    Emitter::default()
        .add_instructions(&build)?
        .add_instructions(&cargo)?
        .add_instructions(&gitcl)?
        .emit()?;

    Ok(())
}
