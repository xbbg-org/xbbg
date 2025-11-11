use pyo3::prelude::*;

#[pymodule]
#[pyo3(name = "_core")]
fn _core(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Keep module empty for scaffold; just ensure it loads.
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    Ok(())
}


