//! xbbg-recipes: High-level Bloomberg recipe functions.
//!
//! Recipes are composed workflows built on top of the xbbg-async engine.
//! Each recipe function takes an Engine reference and performs one or more
//! Bloomberg API calls to produce a final Arrow RecordBatch.
//!
//! Architecture: Recipes call engine.request() directly (no recursion).
//! Recipes are a layer ABOVE the engine, not part of it.

pub mod currency;
pub mod error;
pub mod fixed_income;
pub mod futures;
pub mod historical;

pub use error::{RecipeError, Result};
