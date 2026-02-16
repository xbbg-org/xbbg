//! Recipe error types.

use thiserror::Error;

/// Errors that can occur during recipe execution.
#[derive(Debug, Error)]
pub enum RecipeError {
    /// Error from the Bloomberg async engine.
    #[error("Bloomberg engine error: {0}")]
    Engine(#[from] xbbg_async::BlpAsyncError),

    /// Error from xbbg-ext utilities.
    #[error("Extension utility error: {0}")]
    Ext(#[from] xbbg_ext::ExtError),

    /// Arrow data error.
    #[error("Arrow error: {0}")]
    Arrow(#[from] arrow::error::ArrowError),

    /// Invalid argument provided to a recipe.
    #[error("Invalid argument: {0}")]
    InvalidArgument(String),

    /// General recipe error.
    #[error("Recipe error: {0}")]
    Other(String),
}

/// Result type alias for recipe operations.
pub type Result<T> = std::result::Result<T, RecipeError>;
