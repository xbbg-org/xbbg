//! Currency conversion recipe.
//!
//! Adjusts data columns by fetching FX rates from Bloomberg and applying
//! conversion factors via Arrow compute operations.
//!
//! # Recipes
//!
//! - [`recipe_adjust_ccy`]: Convert data values to a target currency
