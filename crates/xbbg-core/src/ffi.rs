use crate::errors::{BlpError, Result};

#[inline]
#[allow(dead_code)]
pub(crate) fn map_ret(code: i32, context: &str) -> Result<()> {
    if code == 0 {
        Ok(())
    } else {
        Err(BlpError::Internal {
            detail: format!("ffi call failed (code={code}) at {context}"),
        })
    }
}

#[inline]
#[allow(dead_code)]
pub(crate) fn ensure_non_null<T>(ptr: *mut T, context: &str) -> Result<*mut T> {
    if ptr.is_null() {
        Err(BlpError::Internal {
            detail: format!("ffi returned null at {context}"),
        })
    } else {
        Ok(ptr)
    }
}

#[inline]
#[allow(dead_code)]
pub(crate) fn ensure_non_null_const<T>(ptr: *const T, context: &str) -> Result<*const T> {
    if ptr.is_null() {
        Err(BlpError::Internal {
            detail: format!("ffi returned null at {context}"),
        })
    } else {
        Ok(ptr)
    }
}


